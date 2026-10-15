# ORBITALIS-DATA-CENTER

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



## ML

L’objectif du modèle supervisé est de faire de la maintenance prédictive à partir des données analytiques du datacenter orbital.

Le problème est traité comme une classification binaire : pour chaque observation d’un équipement à un instant donné, le modèle doit prédire s’il y aura une maintenance dans une fenêtre donnée.

Trois horizons seront étudiés :

- maintenance_7j
- maintenance_14j
- maintenance_30j

Une cible vaut 1 si une maintenance intervient dans la fenêtre considérée, sinon 0.
```
Exemple :

Observation : 01/05/2026
Maintenance : 10/05/2026

maintenance_7j  = 0
maintenance_14j = 1
maintenance_30j = 1
```

La date complète issue de DIM_TEMPS sera conservée dans le DataFrame pour construire ces cibles et gérer correctement la chronologie.

### Modèles à comparer

Le modèle principal retenu pour le brief est :

**RandomForestClassifier**

Le choix a été fait parmi les deux modèles proposés dans le brief : **Random Forest** ou **Gradient Boosting**.

Random Forest est retenu pour le premier modèle car il est plus simple à interpréter et à mettre en place pour une première approche de maintenance prédictive.

Pour que les résultats aient un point de comparaison, l'entraînement ne reposera pas uniquement sur Random Forest.

On comparera :
```
Baseline naïve
        ->
Régression logistique
        ->
Random Forest
```
La **baseline** permettra de vérifier que le modèle ML apporte réellement quelque chose par rapport à une stratégie triviale.

La **régression logistique** servira de modèle supervisé simple et interprétable.

Le **Random Forest** servira de modèle non linéaire principal.


## Découpage train / test

Les données étant temporelles, il ne faut pas effectuer un découpage aléatoire classique.

On utilisera un découpage chronologique :

passé -> TRAIN

futur -> TEST

Par exemple :

2024-2025 → entraînement
2026      → test

La séparation exacte dépendra de la période disponible dans la BDD analytique.

Cela permet d'éviter une fuite de données où le modèle apprendrait à partir d'événements futurs pour prédire le passé.

## Évaluation

L'accuracy ne sera pas utilisée seule, car les maintenances risquent d'être beaucoup plus rares que les observations sans maintenance.

Les métriques prévues sont :

- Precision
- Recall
- F1-score
- Matrice de confusion
- PR-AUC

Éventuellement :

- ROC-AUC

Le **Recall** sera particulièrement surveillé, car il mesure la proportion de maintenances réellement nécessaires que le modèle a réussi à anticiper.

La **Precision** restera importante également, car une intervention inutile peut être coûteuse dans un environnement orbital.

## Comparaison prévue

Les modèles seront comparés pour chacun des trois horizons :

|Horizon	|Baseline	|Régression logistique	|Random Forest|
|------|--------|--------------|---------|
|7 jours|	métriques|	métriques	|métriques|
|14 jours|	métriques|	métriques|	métriques|
|30 jours|	métriques|	métriques|	métriques|

L'objectif sera notamment de voir si un horizon est plus prédictible qu'un autre.

Par exemple, il est possible que :

- 7 jours
-> signaux très proches de la panne mais peu de temps pour intervenir

- 30 jours
-> davantage de temps pour intervenir mais signaux plus faibles

Ce sera à vérifier avec les résultats réels.

## Organisation des fichiers

Le code ML est séparé en trois fichiers.

analyse_donnees.py

contiendra :

- chargement des données analytiques
- contrôle des colonnes attendues
- préparation des données
- création des features
- création des cibles 7j / 14j / 30j
- matrice de corrélation
- analyses exploratoires
entrainement.py

contiendra :

- sélection de X et y
- séparation temporelle train / test
- baseline
- régression logistique
- Random Forest
- calcul des métriques
- comparaison des modèles
- sauvegarde des modèles entraînés
prediction.py

contiendra :

- chargement du modèle sauvegardé
- préparation des nouvelles données
- prédiction maintenance_7j / 14j / 30j

## Temporalité

La temporalité est volontairement conservée dans les données.

Les features temporelles candidates sont :

`annee`
`mois`
`jour`
`heure`
`minute`

Même si le système se trouve dans l'espace, ces variables ne sont pas conservées pour représenter une saisonnalité terrestre, mais pour permettre au modèle de suivre l'évolution de la dégradation dans le temps.

La colonne :

`date`

sera également conservée dans le DataFrame, mais principalement comme variable technique permettant de :

- trier les observations
- calculer les fenêtres de 7 / 14 / 30 jours
- construire les historiques

Elle ne sera pas utilisée directement comme feature brute du Random Forest.

### Trouver les bonnes features
| Feature candidate          | Groupe                | Justification                                                                                                                     |
| -------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `annee`                    | **Garder**            | Permet de replacer l’observation dans la chronologie globale du dataset et peut capter une dégradation progressive dans le temps. |
| `mois`                     | **Garder**            | Même si la notion de saison terrestre n’est pas centrale ici, le mois reste un repère temporel utile pour suivre l’évolution.     |
| `jour`                     | **Garder**            | Aide à conserver la granularité chronologique et à distinguer des états observés à des dates différentes.                         |
| `heure`                    | **Garder**            | Permet de conserver le contexte temporel fin des mesures et d’éviter de mélanger des observations de moments différents.          |
| `minute_`                  | **Garder**            | Utile si les mesures sont fréquentes et que la dynamique de dégradation ou d’instabilité se voit à petite échelle temporelle.     |
| `type_equipement`          | **Transformer**       | Variable catégorielle importante : les comportements et modes de dégradation peuvent varier selon le type d’équipement.           |
| `altitude_km`              | **Garder**            | Peut refléter des conditions environnementales différentes. À vérifier ensuite avec l’analyse exploratoire.                       |
| `duree_vie_restante`       | **Garder**            | Très pertinente pour la maintenance prédictive, car elle représente directement l’avancement dans le cycle de vie.                |
| `masse_kg`                 | **Retirer au départ** | Peu de lien métier évident avec la dégradation. On pourra la réintégrer si l’analyse montre un signal utile.                      |
| `phase`                    | **Transformer**       | Très importante dans ton contexte orbital, mais catégorielle. Elle permet notamment de distinguer éclipse et ensoleillement.      |
| `rayonnement_solaire_w_m2` | **Garder**            | Décrit directement le contexte énergétique et orbital.                                                                            |
| `temperature_ambiante_c`   | **Garder**            | Les variations thermiques peuvent contribuer au vieillissement ou aux défaillances.                                               |
| `puissance_w`              | **Garder**            | Mesure réelle fondamentale de l’état de fonctionnement de l’équipement.                                                           |
| `puissance_nominale_w`     | **Garder**            | Sert de référence pour évaluer si l’équipement fonctionne à son niveau attendu.                                                   |
| `rayonnement`              | **Garder**            | Peut refléter l’exposition réelle subie par l’équipement.                                                                         |
| `courant_a`                | **Garder**            | Les dérives ou anomalies de courant peuvent être des signes précurseurs de défaillance.                                           |
| `tension_v`                | **Garder**            | Même logique que le courant : une dérive peut signaler un problème électrique.                                                    |
| `temperature_c`            | **Garder**            | Très utile pour détecter surchauffe ou dégradation thermique.                                                                     |
| `rendement_nominal`        | **Garder**            | Permet de comparer le comportement réel avec les caractéristiques prévues du modèle d’équipement.                                 |
| `performance`              | **Garder**            | Indicateur synthétique directement lié à l’écart entre production réelle et attendue.                                             |
| `perte_production`         | **Garder**            | Très pertinent pour identifier une dégradation progressive des performances.                                                      |
| `severite`                 | **Transformer**       | Variable catégorielle pouvant fournir un signal important sur la gravité des événements récents.                                  |
| `acquitte`                 | **Garder**            | Déjà binaire ; peut fournir une information sur le traitement ou la persistance d’une alarme.                                     |
| `type_alarme`              | **Transformer**       | Très utile car les différents types d’alarmes n’ont pas la même signification pour le risque de maintenance.                      |
| `seuil_warning`            | **Transformer**       | La valeur brute seule est difficile à interpréter ; elle sera plus utile sous forme d’écart ou de dépassement de seuil.           |
| `seuil_critical`           | **Transformer**       | Même logique : plus intéressant comme indicateur de dépassem_                                                                     |

## Features historiques prévues

Une partie importante du projet sera de ne pas se limiter à l'état instantané d'un équipement.

Des variables décrivant son évolution seront créées, par exemple :
"""
performance_moyenne_1h
performance_moyenne_24h
variation_performance_24h

temperature_moyenne_1h
temperature_max_24h

variation_tension_1h
variation_courant_1h

nb_alarmes_24h
nb_alarmes_7j

jours_depuis_derniere_maintenance
nb_maintenances_precedentes
"""
Ces features devraient permettre de représenter la dégradation progressive des équipements.

## Evaluation des modèles 
Qu'elles features ils utilisent le plus
