# ORBITALIS DATA CENTER — Analyse exploratoire des données

**Date de l'analyse :** 15 octobre 2026  
**Source :** résultats des requêtes SQL exécutées sur `orbital_data_center_clean.db` et communiqués au cours de notre échange.  
**Objet :** documenter les premiers constats utiles à la qualité des données, à l'analyse de performance et à la future maintenance prédictive.

> **Périmètre et précaution :** le jeu de données a été créé volontairement avec des incohérences. Les résultats ci-dessous décrivent l'état actuel de la base nettoyée après ETL, sans prétendre valider exhaustivement sa qualité. Les exemples de lignes et les agrégats proviennent des sorties SQL communiquées, non d'une inspection directe du fichier SQLite.

## 1. Sources et organisation de la base

Les sources brutes fournies sont `sites.csv`, `equipements.csv`, `telemetrie.csv`, `alarmes.json`, `maintenance.csv`, `orbite.csv` et `catalogue.db`. Le catalogue contient les tables sources `modeles`, `seuils_alarmes` et `references_sites`.

La base SQLite nettoyée comprend huit tables :

| Table | Nombre de lignes | Rôle principal |
|---|---:|---|
| `sites` | 4 | Sites orbitaux |
| `modele` | 12 | Modèles et caractéristiques nominales |
| `equipement` | 64 | Inventaire et rattachement aux sites/modèles |
| `mesure_telemetrie` | 635 040 | Mesures électriques et thermiques |
| `phase_orbitale` | 17 280 | Phase, rayonnement solaire et température ambiante par site |
| `alarmes` | 520 | Alertes par équipement |
| `maintenance` | 96 | Interventions par équipement |
| `seuil_alarme` | 6 | Typologie et seuils d'alarme |

**Requête — volume par table :**

```sql
SELECT 'sites' AS table_source, COUNT(*) AS nb_lignes FROM sites
UNION ALL SELECT 'modele', COUNT(*) FROM modele
UNION ALL SELECT 'equipement', COUNT(*) FROM equipement
UNION ALL SELECT 'mesure_telemetrie', COUNT(*) FROM mesure_telemetrie
UNION ALL SELECT 'phase_orbitale', COUNT(*) FROM phase_orbitale
UNION ALL SELECT 'alarmes', COUNT(*) FROM alarmes
UNION ALL SELECT 'maintenance', COUNT(*) FROM maintenance
UNION ALL SELECT 'seuil_alarme', COUNT(*) FROM seuil_alarme;
```

**Relations importantes :** une mesure est rattachée à un équipement, lui-même rattaché à un site et à un modèle. Une phase orbitale dépend d'un site et d'un instant. Les alarmes et interventions de maintenance sont rattachées à un équipement. Pour rapprocher télémétrie et orbite, il faut combiner `site_id` et une règle de correspondance temporelle.

## 2. Exploration d'un échantillon d'équipements

Une première jointure entre télémétrie, équipements, modèles et orbite a permis d'observer notamment :

- des panneaux solaires, des convertisseurs DC et des batteries ;
- des puissances nominales de 1 000 à 2 500 W dans les vingt lignes consultées ;
- des durées de vie théoriques de 8 à 15 ans dans cet échantillon ;
- l'équipement `EQ-005` avec le statut `maintenance` ;
- deux lignes `EQ-006` au même timestamp (`2025-05-01 00:00:00`).

La répétition de `EQ-006` **ne suffit pas** à conclure à un doublon : il faut examiner les identifiants de mesure et les autres champs. Dans l'extrait transmis, plusieurs colonnes après le timestamp n'étaient pas visibles ; leur présence ou leur absence ne peut donc pas être déduite de cet affichage.

**Requête utilisée :**

```sql
SELECT
    e.equipement_id, e.site_id, e.date_installation, e.statut,
    m.type_equipement, m.puissance_nominale_w,
    m.rendement_nominal, m.duree_vie_annees,
    t.timestamp, t.puissance_w, t.temperature_c,
    t.tension_v, t.courant_a, t.rayonnement,
    o.phase, o.rayonnement_solaire_w_m2, o.temperature_ambiante_c
FROM mesure_telemetrie t
LEFT JOIN equipement e ON t.equipement_id = e.equipement_id
LEFT JOIN modele m ON e.modele_id = m.modele_id
LEFT JOIN phase_orbitale o
    ON e.site_id = o.site_id AND t.timestamp = o.timestamp
ORDER BY t.timestamp
LIMIT 20;
```

## 3. Couverture de la télémétrie et des maintenances

| Indicateur | Résultat |
|---|---|
| Premier timestamp de télémétrie | `2025-05-01 00:00:00` |
| Dernier timestamp de télémétrie | `2025-06-14 23:55:00` |
| Mesures de télémétrie | 635 040 |
| Équipements distincts avec télémétrie | 48 |
| Équipements dans l'inventaire | 64 |
| Première maintenance (date de début) | `2025-05-01 00:00:00` |
| Dernière maintenance (date de début) | `2025-06-10 00:00:00` |
| Interventions | 96 |
| Équipements distincts maintenus | 44 |

La télémétrie couvre **45 jours calendaires**, tandis que les dates de début des maintenances vont du 1er mai au 10 juin 2025. **16 équipements de l'inventaire ne figurent pas dans la télémétrie** ; cette différence nécessite une vérification. On ne sait pas encore si ces équipements sont hors service, non instrumentés ou absents pour une autre raison.

**Requêtes utilisées :**

```sql
SELECT MIN(timestamp) AS premiere_mesure,
       MAX(timestamp) AS derniere_mesure,
       COUNT(DISTINCT equipement_id) AS nb_equipements,
       COUNT(*) AS nb_mesures
FROM mesure_telemetrie;

SELECT MIN(date_debut) AS premiere_maintenance,
       MAX(date_debut) AS derniere_maintenance,
       COUNT(*) AS nb_maintenances,
       COUNT(DISTINCT equipement_id) AS nb_equipements_maintenus
FROM maintenance;
```

**Conséquence pour le ML :** les horizons de 7, 14 et surtout 30 jours envisagés initialement pour prédire les maintenances sont difficiles à évaluer avec une fenêtre de télémétrie de 45 jours. L'horizon de **9 heures** demandé par le brief est plus adapté à la couverture temporelle, sans pour autant garantir un nombre suffisant d'événements de dégradation indépendants.

## 4. Typologie des opérations de maintenance

| Type d'intervention | Nombre | Équipements distincts | Coût moyen enregistré |
|---|---:|---:|---:|
| `remplacement` | 25 | 18 | 3 791,76 € |
| `inspection` | 25 | 22 | 3 583,92 € |
| `preventive` | 18 | 17 | 2 842,00 € |
| `calibration` | 16 | 14 | 2 972,81 € |
| `corrective` | 12 | 11 | 3 091,58 € |
| **Total** | **96** | — | — |

**Requête utilisée :**

```sql
SELECT type_intervention,
       COUNT(*) AS nb_interventions,
       COUNT(DISTINCT equipement_id) AS nb_equipements,
       ROUND(AVG(cout_eur), 2) AS cout_moyen_eur
FROM maintenance
GROUP BY type_intervention
ORDER BY nb_interventions DESC;
```

**Interprétation :** une maintenance ne prouve pas automatiquement une dégradation. Une inspection ou une calibration peut être programmée, tout comme une maintenance préventive ; un remplacement peut être planifié ou correctif. Les 12 interventions explicitement `corrective` ne suffisent pas à elles seules pour définir toutes les dégradations. Une cible « maintenance dans N jours » représenterait donc une question métier différente de « dégradation dans les 9 prochaines heures ».

Les coûts moyens ci-dessus sont les valeurs enregistrées dans la table de maintenance ; **ils ne doivent pas être confondus** avec la matrice de coût métier imposée pour évaluer le classifieur.

## 5. Alarmes : niveaux de sévérité et types

**Requête utilisée :**

```sql
SELECT s.type_alarme, a.severite,
       COUNT(*) AS nb_alarmes,
       COUNT(DISTINCT a.equipement_id) AS nb_equipements
FROM alarmes a
LEFT JOIN seuil_alarme s ON a.id_seuil = s.id_seuil
GROUP BY s.type_alarme, a.severite
ORDER BY s.type_alarme, a.severite;
```

**Résultats transmis :**

| Type d'alarme | `critical` | `warning` | `info` | Autre |
|---|---:|---:|---:|---|
| `capteur_defaillant` | 39 | 36 | 15 | 1 `URGENCE` |
| `perte_puissance` | 29 | 48 | 12 | — |
| `sous_tension` | 30 | 31 | 19 | — |
| `surcharge` | 31 | 48 | 18 | — |
| `surchauffe` | 44 | 28 | 11 | — |
| `vibration_anormale` | 36 | 28 | 15 | — |
| **Total de ces catégories** | **209** | **219** | **110** | **1** |

Une ligne supplémentaire apparaît avec un **type d'alarme absent** dans la jointure et une sévérité `warning` (1 occurrence, 1 équipement). Le total de tous les groupes fournis est bien **540**, alors que la table `alarmes` contient **520 lignes** : **cette incohérence entre résultats transmis doit être revérifiée** (par exemple en relançant les agrégats sur la même version de la base et en vérifiant d'éventuelles duplications lors de la jointure à `seuil_alarme`).

Parmi les alarmes critiques candidates à la cible du brief : `surchauffe` (44), `perte_puissance` (29) et éventuellement `surcharge` (31), soit **104 événements critiques comptés dans ces trois catégories**. Leur pertinence exacte et l'inclusion de `surcharge` doivent être confirmées selon le sens métier. Il ne s'agit pas nécessairement de 104 épisodes indépendants.

**Contrôles suggérés :**

```sql
-- Vérifier le nombre de lignes et la répartition brute des sévérités
SELECT severite, COUNT(*) FROM alarmes GROUP BY severite;

-- Vérifier l'unicité de type_alarme dans le référentiel des seuils
SELECT type_alarme, COUNT(*) AS nb
FROM seuil_alarme
GROUP BY type_alarme
HAVING COUNT(*) > 1;
```

## 6. Production et ratio puissance réelle / nominale

La requête suivante a été utilisée comme **premier diagnostic**, et non comme mesure validée de la santé des équipements :

```sql
SELECT
    m.type_equipement,
    COUNT(*) AS nb_mesures,
    ROUND(AVG(t.puissance_w), 2) AS puissance_moyenne_w,
    ROUND(AVG(m.puissance_nominale_w), 2) AS puissance_nominale_moyenne_w,
    ROUND(AVG(CASE WHEN m.puissance_nominale_w > 0
                   THEN t.puissance_w / m.puissance_nominale_w END), 3)
        AS performance_moyenne
FROM mesure_telemetrie t
JOIN equipement e ON t.equipement_id = e.equipement_id
JOIN modele m ON e.modele_id = m.modele_id
GROUP BY m.type_equipement
ORDER BY m.type_equipement;
```

| Type | Mesures | Puissance mesurée moyenne | Puissance nominale moyenne | Ratio moyen |
|---|---:|---:|---:|---:|
| `batterie` | 155 520 | 277,51 W | 1 500 W | 0,185 |
| `convertisseur_DC` | 155 520 | 797,57 W | 1 700 W | 0,466 |
| `panneau_solaire` | 324 000 | 572,89 W | 1 660 W | 0,325 |

**Prudence :** `puissance_w / puissance_nominale_w` décrit ici surtout un rapport à la capacité nominale. Ce n'est pas nécessairement la `performance = puissance_reelle / puissance_attendue` demandée par le brief. La puissance attendue devrait être définie selon le type d'équipement, son mode de fonctionnement et le contexte orbital. Une batterie au repos ou un convertisseur à charge partielle n'est pas automatiquement dégradé.

## 7. Performance apparente selon la phase orbitale

**Requête utilisée :**

```sql
SELECT
    m.type_equipement,
    o.phase,
    COUNT(*) AS nb_mesures,
    ROUND(AVG(t.puissance_w), 2) AS puissance_moyenne_w,
    ROUND(AVG(CASE WHEN m.puissance_nominale_w > 0
                   THEN t.puissance_w / m.puissance_nominale_w END), 3)
        AS performance_moyenne
FROM mesure_telemetrie t
JOIN equipement e ON t.equipement_id = e.equipement_id
JOIN modele m ON e.modele_id = m.modele_id
LEFT JOIN phase_orbitale o
    ON e.site_id = o.site_id AND t.timestamp = o.timestamp
GROUP BY m.type_equipement, o.phase
ORDER BY m.type_equipement, o.phase;
```

| Type | Phase | Mesures | Puissance moyenne | Ratio moyen |
|---|---|---:|---:|---:|
| Batterie | `NULL` | 103 680 | 277,10 W | 0,185 |
| Batterie | `eclipse` | 19 413 | 264,43 W | 0,176 |
| Batterie | `ensoleillement` | 32 337 | 286,72 W | 0,191 |
| Batterie | `inconnu` | 90 | 268,11 W | 0,179 |
| Convertisseur DC | `NULL` | 103 680 | 797,62 W | 0,466 |
| Convertisseur DC | `eclipse` | 19 413 | 138,71 W | 0,081 |
| Convertisseur DC | `ensoleillement` | 32 337 | 1 192,82 W | 0,698 |
| Convertisseur DC | `inconnu` | 90 | 836,05 W | 0,517 |
| Panneau solaire | `NULL` | 216 000 | 572,61 W | 0,324 |
| Panneau solaire | `eclipse` | 40 445 | 0,00 W | 0,000 |
| Panneau solaire | `ensoleillement` | 67 370 | 917,56 W | 0,520 |
| Panneau solaire | `inconnu` | 185 | 635,99 W | 0,360 |

Les phases `NULL` regroupent **423 360 mesures sur 635 040**, soit **66,7 %** de toutes les lignes (dans cette jointure exacte). Ce volume reflète principalement la différence de fréquence entre télémétrie et orbite et **ne doit pas être automatiquement interprété comme 66,7 % de phases réellement manquantes à la source**.

**Constats métier :**

- Les panneaux solaires présentent 0 W en éclipse dans cet agrégat : c'est cohérent avec une absence normale de production solaire.
- Les convertisseurs DC ont un ratio moyen beaucoup plus faible en éclipse (0,081) qu'en ensoleillement (0,698) ; une puissance réduite ne signifie pas automatiquement une panne.
- Les batteries ont des niveaux similaires entre les deux phases (0,176 et 0,191) ; leur fonctionnement requiert une interprétation spécifique (charge, décharge, repos).
- Même en ensoleillement, le ratio moyen des panneaux solaires est de 0,520 : appliquer mécaniquement un seuil de 0,65 à ce ratio serait risqué.

## 8. Granularité temporelle : raison des phases `NULL`

**Requête utilisée :**

```sql
SELECT 'telemetrie' AS source,
       MIN(timestamp) AS premiere_date,
       MAX(timestamp) AS derniere_date,
       COUNT(*) AS nb_lignes,
       COUNT(DISTINCT timestamp) AS nb_timestamps
FROM mesure_telemetrie
UNION ALL
SELECT 'orbite', MIN(timestamp), MAX(timestamp),
       COUNT(*), COUNT(DISTINCT timestamp)
FROM phase_orbitale;
```

| Source | Début | Fin | Lignes | Timestamps distincts | Pas théorique |
|---|---|---|---:|---:|---|
| Télémétrie | 01/05/2025 00:00 | 14/06/2025 23:55 | 635 040 | 12 960 | 5 minutes |
| Orbite | 01/05/2025 00:00 | 14/06/2025 23:45 | 17 280 | 4 320 | 15 minutes |

Sur 45 jours : `45 × 24 × 12 = 12 960` timestamps de télémétrie et `45 × 24 × 4 = 4 320` timestamps orbitaux. La télémétrie est donc observée toutes les **5 minutes**, et l'orbite toutes les **15 minutes** au niveau des timestamps distincts.

Une jointure `t.timestamp = o.timestamp` ne trouve un relevé orbital que pour un timestamp de télémétrie sur trois, d'où les `NULL` observés. De plus, la phase `inconnu` existe réellement et doit être distinguée de l'absence de correspondance.

**Règle de rapprochement candidate :** rattacher les mesures d'un site à la dernière phase orbitale connue (par exemple 10h05 et 10h10 associés au relevé orbital de 10h00), avec une tolérance temporelle explicite. Une jointure de type `merge_asof(..., direction="backward", by="site_id")` est envisageable, **à condition de confirmer** qu'un relevé orbital est valable jusqu'au suivant. Cela évite d'associer la télémétrie à une observation future, contrairement à certains arrondis à la quinzaine de minutes la plus proche.

## 9. Implications pour la maintenance prédictive

### 9.1 Objectif métier à privilégier

Le brief impose de prédire à l'instant `t` une **dégradation dans les 9 prochaines heures** (ou six périodes orbitales), et propose comme cible :

- performance moyenne future **hors éclipse** inférieure à 0,65 ; **OU**
- alarme `critical` future liée à la puissance ou à la température.

**Cette cible n'est pas encore implémentée ni validée.** La définition de `puissance_attendue` et l'applicabilité du seuil 0,65 selon le type d'équipement doivent être précisées avant d'étiqueter les observations.

Les anciennes cibles de maintenance à 7/14/30 jours restent éventuellement une analyse secondaire, et ne satisfont pas directement l'objectif obligatoire.

### 9.2 Modèles retenus pour la comparaison

1. **Baseline naïve**, comme point de comparaison.
2. **Régression logistique**, modèle supervisé simple et interprétable.
3. **Random Forest Classifier**, pour les interactions et relations non linéaires entre variables.

Le découpage devra suivre le temps : **entraînement → validation → test**, en prévoyant le traitement des fenêtres futures de 9 heures aux frontières pour éviter toute fuite d'information.

### 9.3 Métriques et coût métier

L'accuracy seule pourrait masquer une mauvaise détection si les événements positifs sont rares. Leur rareté doit encore être mesurée sur la cible définitive. Les métriques prévues sont : **Precision, Recall, F1-score, matrice de confusion, PR-AUC**, et éventuellement ROC-AUC.

Le brief définit les coûts suivants :

| Résultat | Coût métier |
|---|---:|
| Vrai positif : dégradation anticipée | 300 € |
| Faux positif : inspection inutile | 150 € |
| Faux négatif : dégradation non anticipée | 2 500 € |
| Vrai négatif : pas d'intervention nécessaire | 0 € |

Coût total : `300 × VP + 150 × FP + 2 500 × FN`.

Le **Recall** aide à limiter les dégradations manquées, tandis que la **Precision** aide à limiter les inspections inutiles. Le seuil de décision doit être **choisi sur la validation en minimisant le coût métier**, puis appliqué une seule fois au jeu de test.

### 9.4 Features candidates à réévaluer

- **Équipement :** `type_equipement`, puissance nominale, rendement nominal, âge calculé à la date `t`, site ; durée de vie restante seulement si calculable sans information future.
- **Contexte :** phase orbitale correctement rattachée, rayonnement solaire et température ambiante.
- **Mesures :** puissance, tension, courant, température, rayonnement ; indicateurs de performance **définis selon le métier**.
- **Historique jusqu'à `t` :** moyenne et évolution de performance, température maximale récente, évolution courant/tension, nombre d'alarmes précédentes, temps depuis la dernière maintenance connue.
- **Calendrier :** les variables année, mois, jour, heure et minute ne doivent pas être conservées systématiquement ; évaluer leur sens physique, leur utilité et leur risque de surapprentissage.

**Attention à la fuite de données :** le traitement ETL actuel utilise notamment interpolation linéaire et `bfill()`, qui peuvent exploiter des mesures futures. Les imputations devront être revues ou évaluées dans un cadre strictement temporel pour l'entraînement et l'inférence. Une alarme ou une maintenance postérieure à `t` peut définir la cible, mais ne doit pas entrer dans les features connues à `t`.

## 10. Points restant à vérifier avant le développement ML

1. Vérifier pourquoi **16 équipements** de l'inventaire n'ont pas de télémétrie et quels types sont concernés.
2. Corriger/justifier les **écarts de totaux d'alarmes** (540 dans l'agrégation transmise contre 520 dans la table).
3. Contrôler les sévérités non standard (`URGENCE`), types d'alarme sans correspondance et références non uniques.
4. Définir la **puissance attendue** par famille d'équipements, au lieu d'assimiler systématiquement nominal et attendu.
5. Vérifier le sens métier de la phase, des périodes `inconnu` et la méthode de jointure temporelle site/timestamp.
6. Évaluer les valeurs corrigées ou reconstruites par ETL et identifier les imputations utilisant le futur.
7. Contrôler doublons de télémétrie, timestamps invalides et relations entre identifiants.
8. Mesurer la distribution des **vrais événements positifs** après définition de la cible et le nombre d'équipements touchés.
9. Déterminer la fenêtre de création des exemples, les features historiques et les frontières train/validation/test.
10. Réviser le README et `analyse_donnees.py` après validation de la cible, puis implémenter `entrainement.py` et `prediction.py`.

---

**Conclusion provisoire :** les données sont suffisantes pour démarrer la conception d'une classification supervisée, mais pas encore pour affirmer qu'un seuil de performance donné décrit une dégradation réelle. Le principal enjeu est de construire une cible métier mesurable qui tienne compte des éclipses, des modes de fonctionnement des équipements et de la disponibilité temporelle des informations.
