# ORBITALIS DATA CENTER

## Objectif du projet

Construire une chaîne de données reproductible pour analyser les performances des équipements électriques d'un datacenter en orbite basse et **anticiper une dégradation dans les 9 prochaines heures** (ou six périodes orbitales, selon le cadrage du brief).

Les données sont volontairement imparfaites : il faut distinguer les anomalies de mesure, les comportements physiques normaux et les dégradations réelles. **Une puissance solaire nulle pendant une éclipse n'est pas une panne.**

> **État du projet :** ETL et base relationnelle SQLite présentés ; scripts ML préparés, mais chargement analytique, construction de cible, entraînement et prédiction encore à implémenter. Les choix décrits ci-dessous constituent le plan de travail, pas des résultats de modèle déjà obtenus.

## 1. Sources, ETL et exploration

Sept sources brutes : `sites.csv`, `equipements.csv`, `telemetrie.csv`, `orbite.csv`, `maintenance.csv`, `alarmes.json` et `catalogue.db` (tables `modeles`, `seuils_alarmes`, `references_sites`).

L'ETL est organisé en `extract.py`, `transform.py` et `load.py`. La base relationnelle créée est `orbital_data_center_clean.db` :

| Table SQLite | Lignes constatées |
|---|---:|
| `sites` | 4 |
| `modele` | 12 |
| `equipement` | 64 |
| `mesure_telemetrie` | 635 040 |
| `phase_orbitale` | 17 280 |
| `alarmes` | 520 |
| `maintenance` | 96 |
| `seuil_alarme` | 6 |

La télémétrie va du **01/05/2025 00:00** au **14/06/2025 23:55** et concerne **48 équipements** sur les **64 référencés**. Les maintenances vont du **01/05/2025** au **10/06/2025**, avec **44 équipements concernés**.

La télémétrie compte **12 960 timestamps distincts** (pas théorique de **5 minutes**) ; l'orbite **4 320** (pas théorique de **15 minutes**). La phase orbitale est rattachée au **site et au temps**, pas directement à la mesure. Une jointure sur l'égalité stricte des timestamps laisse beaucoup de phases non renseignées : envisager le dernier état orbital connu (`merge_asof` en arrière, avec tolérance et contrôle des cas inconnus), après vérification de la signification temporelle des relevés. Il ne faut pas utiliser une phase future pour prédire au temps `t`.

### Constat sur le ratio puissance / puissance nominale

| Type | Toutes phases confondues | Éclipse | Ensoleillement |
|---|---:|---:|---:|
| Batterie | 0,185 | 0,176 | 0,191 |
| Convertisseur DC | 0,466 | 0,081 | 0,698 |
| Panneau solaire | 0,325 | 0,000 | 0,520 |

*Valeurs observées lors des requêtes SQL. Les colonnes par phase ne couvrent que les lignes qui ont effectivement pu être associées à une phase par égalité exacte ; elles ne représentent donc pas nécessairement toutes les observations. Le ratio ci-dessus est un **taux de puissance nominale utilisée**, pas automatiquement un indicateur de santé.*

Un panneau solaire doit être analysé selon l'ensoleillement et le rayonnement. Une batterie peut charger, décharger ou être au repos ; un convertisseur peut fonctionner à charge partielle. La **puissance attendue** doit être définie avec les hypothèses métier adaptées aux types d'équipements avant d'utiliser un seuil de performance.

### Alarmes et maintenances

Les maintenances se répartissent ainsi : `remplacement` 25, `inspection` 25, `preventive` 18, `calibration` 16, `corrective` 12. Une maintenance n'implique pas automatiquement une dégradation ; c'est pourquoi **prédire une maintenance** n'est pas l'équivalent de **prédire une dégradation**.

Les alarmes critiques relevées incluent : `surchauffe` 44, `perte_puissance` 29, `surcharge` 31, `sous_tension` 30, `capteur_defaillant` 39 et `vibration_anormale` 36. Une sévérité `URGENCE` apparaît aussi et doit être examinée. Avant d'interpréter les totaux par catégorie, vérifier l'unicité de `type_alarme` dans le référentiel : le regroupement effectué par jointure donnait plus de lignes que les **520** alarmes de la table.

Pour les constats détaillés et les requêtes SQL d'exploration, voir `documentation/synthèse.md` (brut) et `documentation/analyse_donnee.md` (base chargée), selon l'emplacement réel de ces fichiers dans le dépôt.

## 2. SQL et analyse décisionnelle

Questions du brief à traiter dans le schéma analytique : production énergétique par équipement et par jour ; performance hors éclipse ; alarmes par sévérité ; intervalle entre maintenances ; équipements sans maintenance depuis 90 jours ; pertes en kWh par site ; évolution temporelle avec fonction de fenêtre ; comparaison des phases orbitales ; coût estimé des pertes ; optimisation d'une requête par `EXPLAIN QUERY PLAN` et index.

### Production énergétique journalière (à valider)

Une somme de puissances en W n'est **pas** une énergie. **Si** chaque valeur est représentative d'un intervalle de 5 minutes, l'énergie en kWh est approximativement `SUM(puissance_w * 5 / 60 / 1000)`. Ne pas appliquer aveuglément cette approximation en présence de doublons d'horodatage, de trous, ou de mesures non représentatives d'un intervalle.

```sql
-- Estimation conditionnelle : une mesure représentative toutes les 5 minutes.
SELECT
    equipement_id,
    DATE(timestamp) AS jour,
    ROUND(SUM(puissance_w) * 5.0 / 60.0 / 1000.0, 3) AS energie_kwh_estimee
FROM mesure_telemetrie
GROUP BY equipement_id, DATE(timestamp)
ORDER BY jour, equipement_id;
```

Les autres requêtes SQL restent à documenter dans cette section au fur et à mesure de leur validation.

## 3. Machine Learning : objectif et variable cible

### Problème principal — classification binaire

Pour chaque **équipement** à une **date de référence `t`**, prédire s'il entre dans un état dégradé dans les **9 heures suivantes**.

- `risque_degradation_9h = 1` : au moins un critère de dégradation confirmé se produit dans `(t, t + 9h]`.
- `risque_degradation_9h = 0` : aucun critère ne se produit pendant une fenêtre **entièrement observable**.
- Cible **indéterminée / exclue** si la fenêtre future n'est pas entièrement observable ou si les données nécessaires pour statuer sont insuffisantes.

**Définition candidate, conforme à l'exemple du brief** (à valider avant codage) :

1. Performance moyenne d'un équipement **hors éclipse**, calculée sur les observations pertinentes de la fenêtre future, inférieure à **0,65**, **OU**
2. Au moins une alarme `critical` liée à la puissance ou à la température pendant cette même fenêtre (`perte_puissance`, `surchauffe`, éventuellement `surcharge` après validation métier).

**Points à trancher avant de calculer la cible :** calcul défendable de `puissance_attendue` pour chaque type d'équipement ; traitement des batteries et convertisseurs ; nombre minimal de mesures hors éclipse ; rattachement des alarmes par `equipement_id` et timestamp ; normalisation éventuelle de sévérités atypiques. Un ratio `puissance_w / puissance_nominale_w < 0,65` **ne suffit pas** à constater une panne.

La cible utilise des événements futurs pour établir **l'étiquette** lors de l'entraînement, mais aucune donnée future ne doit entrer dans les **features** disponibles à `t`.

### Piste secondaire

L'étude initialement envisagée des cibles `maintenance_7j`, `maintenance_14j` et `maintenance_30j` est **reportée en bonus exploratoire** : elle prédit des interventions (dont certaines planifiées), et non directement une dégradation. Une fenêtre de 30 jours est difficile à étudier avec seulement 45 jours de télémétrie ; les derniers instants sans horizon complet ne doivent pas être étiquetés négatifs.

## 4. Modèles à comparer

1. **Baseline naïve** : stratégie triviale documentée servant de comparaison (par exemple « aucun risque »), y compris son coût métier.
2. **Régression logistique** : modèle supervisé de classification simple et interprétable ; nécessite un prétraitement adapté (encodage des catégories, gestion des manquants, mise à l'échelle des variables quantitatives selon le pipeline retenu).
3. **RandomForestClassifier** : modèle supervisé non linéaire, capable de capter des interactions entre mesures, type d'équipement et contexte orbital ; encodage et gestion des manquants également nécessaires.

**Deux modèles supervisés principaux** : régression logistique et Random Forest. Le modèle retenu sera choisi **sur les résultats de validation et le coût métier**, pas fixé d'avance.

## 5. Temporalité et validation

**Période observée : 1er mai au 14 juin 2025** ; le découpage envisagé dans l'ancien README (`2024–2025` / `2026`) n'est pas compatible avec la télémétrie disponible.

Séparation **chronologique** en trois ensembles distincts :

`TRAIN (passé) → VALIDATION (plus récent) → TEST (fin de période)`.

Les dates exactes seront choisies après analyse de la fréquence des événements positifs. Les observations de tous les équipements seront séparées selon le **même axe temporel**. Prévoir une **purge/embargo d'au moins 9 heures aux frontières**, et davantage si les features historiques ou les règles de construction des observations le requièrent, pour éviter le chevauchement d'information entre partitions. Les paramètres de prétraitement ne doivent être ajustés que sur le train.

Sur la **validation** : comparer les modèles et choisir **un seuil de décision** minimisant le coût métier. Sur le **test** : appliquer **une seule fois** le modèle et le seuil choisis, sans les réajuster.

## 6. Évaluation et coût métier

Si les dégradations positives sont minoritaires (hypothèse **à vérifier** après création de la cible), l'**accuracy seule** peut être trompeuse : prédire toujours la classe majoritaire peut obtenir un score élevé sans détecter de dégradation.

Mesures prévues : **matrice de confusion**, **Recall**, **Precision**, **F1-score**, **PR-AUC** (aire sous la courbe précision-rappel) ; **ROC-AUC** en complément si elle est définie pour les classes présentes. Toujours comparer à la fréquence de base des positifs.

Le **Recall** quantifie les dégradations réellement détectées : les faux négatifs sont coûteux. La **Precision** renseigne sur la proportion d'alertes pertinentes : trop de faux positifs entraîneraient des inspections inutiles. Ni l'un ni l'autre n'est le critère final à lui seul.

| Réalité / Décision | Prédire un risque (inspecter) | Ne pas prédire de risque |
|---|---:|---:|
| Dégradation réelle | **VP = 300 €** | **FN = 2 500 €** |
| Aucune dégradation | **FP = 150 €** | **VN = 0 €** |

`cout_total = 300 × VP + 150 × FP + 2500 × FN`.

Une fois les probabilités prédites sur validation, tester différents seuils et sélectionner celui dont le coût total est minimal ; appliquer ensuite ce seuil sur le jeu de test. Ce calcul tient compte du fait qu'une dégradation manquée coûte bien plus cher qu'une inspection inutile.

## 7. Features : première sélection à confirmer

Le jeu ML doit avoir **une ligne par équipement et date de décision `t`**, et non une multiplication de lignes liée à des jointures directes entre chaque mesure, chaque alarme et chaque maintenance.

| Groupe | Variables candidates | Décision et précautions |
|---|---|---|
| Identification | `equipement_id`, `site_id`, `date_` | Clés de rapprochement, tri, constitution des historiques ; **pas de variables brutes d'identifiant** dans le premier modèle |
| Équipement | `type_equipement`, `puissance_nominale_w`, `rendement_nominal`, `altitude_km` | Garder comme candidates ; encoder le type, vérifier le pouvoir explicatif et les manquants |
| Vieillissement | `date_installation`, `duree_vie_annees` | Calculer **âge à `t`** et éventuellement durée théorique restante, sans information future |
| Orbite | `phase`, `rayonnement_solaire_w_m2`, `temperature_ambiante_c` | Garder ; rattacher au dernier état connu et encoder la phase ; traiter `inconnu` séparément |
| Télémétrie | `puissance_w`, `tension_v`, `courant_a`, `temperature_c`, `rayonnement` | Garder comme candidates si valides et connues à `t` ; tenir compte des imputations |
| Performance et pertes | `performance`, `perte_production` | **À redéfinir** avec une puissance attendue défendable ; ne pas assimiler automatiquement puissance nominale et attendue |
| Alarmes | `severite`, `type_alarme`, `acquittee` | Préférer des **comptages et indicateurs historiques avant `t`** aux alarmes jointes sans filtre temporel |
| Seuils | `seuil_warning`, `seuil_critical` | Utiliser seulement si comparables avec une grandeur physique précise ; éventuellement écarts au seuil |
| Maintenance | interventions passées | `jours_depuis_derniere_maintenance`, nombre d'interventions **avant `t`** ; jamais la maintenance future |
| Calendrier | `annee`, `mois`, `jour`, `heure`, `minute_` | `date_` conservée pour le tri ; **ne pas inclure par défaut** année/mois/jour/minute comme variables : peu d'historique et risque d'apprendre la date plutôt que la dégradation. Tester éventuellement l'heure si justifiée |
| Autre | `masse_kg` | Écarter au départ, réévaluer si une analyse établit son utilité |
| Qualité de la donnée | indicateurs d'imputation et de lacunes | À créer idéalement dans l'ETL : une mesure reconstruite peut masquer un signal de défaillance |

**Features historiques prioritaires (calculées uniquement à partir des temps ≤ `t`) :**

- `performance_moyenne_1h`, `performance_moyenne_24h`, `variation_performance_24h` (quand la performance est correctement définie)
- `temperature_moyenne_1h`, `temperature_max_24h`
- `variation_tension_1h`, `variation_courant_1h`
- `nb_alarmes_24h`, `nb_alarmes_7j`, `nb_alarmes_critiques_24h`
- `jours_depuis_derniere_maintenance`, `nb_maintenances_precedentes`
- `nb_mesures_manquantes_1h`, indicateurs de valeurs interpolées, si leur traçabilité est disponible

Les historiques longs (24 h, 7 j) demandent une période d'observation préalable suffisante. Exclure ou gérer les fenêtres initiales incomplètes. Toute interpolation centrée ou `bfill` utilisant des valeurs futures doit être revue pour les variables du modèle prédictif.

## 8. Organisation du code ML

### `analyse_donnees.py`

- Charger la base analytique (**connexion à compléter**).
- Vérifier le grain et les colonnes réellement disponibles ; harmoniser `date_`, `minute_`, les ID et les noms de colonnes.
- Rapprocher les sources sans dupliquer artificiellement les observations.
- Construire les features disponibles à `t` et la cible `risque_degradation_9h` à partir de la période suivante.
- Réaliser les analyses exploratoires, la vérification de l'équilibre des classes et la matrice de corrélation.

### `entrainement.py`

- Définir `X` et `y` ; découper chronologiquement train / validation / test.
- Entraîner baseline, régression logistique et Random Forest avec prétraitements adaptés.
- Calculer métriques et matrices de confusion.
- Choisir sur validation le modèle et le seuil minimisant le coût métier.
- Évaluer une seule fois sur test, puis sauvegarder modèle, prétraitement, colonnes et seuil.

### `prediction.py`

- Charger le pipeline, la liste des variables et le seuil retenu.
- Préparer une nouvelle observation avec **le même schéma de features** et uniquement des données connues au temps de prédiction.
- Fournir la probabilité de dégradation à 9 heures et la décision d'inspection associée.

## 9. Points restant à vérifier avant codage de l'entraînement

1. Définir la **puissance attendue** par type d'équipement ; valider le sens métier du seuil `0,65`, surtout pour les batteries et les convertisseurs.
2. Vérifier la qualité de la correspondance orbitale (site, timestamp, `inconnu`) et l'absence d'utilisation d'informations futures.
3. Vérifier la cardinalité de `seuil_alarme.type_alarme` et les écarts observés dans les décomptes d'alarmes.
4. Déterminer le **nombre d'exemples positifs et négatifs** une fois la cible construite, par équipement et par segment chronologique.
5. Définir la fréquence des instants de décision (`t`, par exemple toutes les 15 minutes), le minimum de données requis et les règles de gestion des fenêtres non observables.
6. Contrôler les imputations de l'ETL et conserver des indicateurs de correction lorsque possible.
7. Valider les dates de train, validation et test ainsi que les éventuels trous/purges temporelles.

---

**Principe directeur :** l'objectif n'est pas de prédire davantage de maintenances planifiées, mais d'**anticiper des dégradations réelles** en minimisant le coût des mauvaises décisions, sans confondre éclipse, charge partielle et panne.
