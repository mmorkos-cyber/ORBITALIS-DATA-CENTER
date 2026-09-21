# Synthèse d'exploration

## Exploration des CSV

equipement.csv :
```powershell
RangeIndex: 67 entries, 0 to 66
Data columns (total 7 columns):
 #   Column                Non-Null Count  Dtype
---  ------                --------------  -----
 0   equipement_id         67 non-null     str  
 1   site_id               66 non-null     str  
 2   type                  67 non-null     str  
 3   modele                66 non-null     str  
 4   puissance_nominale_w  67 non-null     int64
 5   date_installation     67 non-null     str  
 6   statut                67 non-null     str  
dtypes: int64(1), str(6)
memory usage: 7.6 KB
None
equipement_id           0
site_id                 1
type                    0
modele                  1
puissance_nominale_w    0
date_installation       0
statut                  0
dtype: int64
(67, 7)
1
```
maintenance.csv :
```powershell
RangeIndex: 97 entries, 0 to 96
Data columns (total 8 columns):
 #   Column             Non-Null Count  Dtype
---  ------             --------------  -----
 0   maintenance_id     97 non-null     str  
 1   equipement_id      96 non-null     str  
 2   date_debut         97 non-null     str  
 3   date_fin           97 non-null     str  
 4   type_intervention  97 non-null     str  
 5   technicien         84 non-null     str  
 6   cout_eur           97 non-null     int64
 7   commentaire        63 non-null     str  
dtypes: int64(1), str(7)
memory usage: 12.0 KB
None
maintenance_id        0
equipement_id         1
date_debut            0
date_fin              0
type_intervention     0
technicien           13
cout_eur              0
commentaire          34
dtype: int64
(97, 8)
0
```
orbite.csv :
```powershell
RangeIndex: 17280 entries, 0 to 17279
Data columns (total 5 columns):
 #   Column                    Non-Null Count  Dtype  
---  ------                    --------------  -----  
 0   timestamp                 17280 non-null  str    
 1   site_id                   17280 non-null  str    
 2   phase                     17280 non-null  str    
 3   rayonnement_solaire_w_m2  17280 non-null  float64
 4   temperature_ambiante_c    17265 non-null  float64
dtypes: float64(2), str(3)
memory usage: 1.3 MB
None
timestamp                    0
site_id                      0
phase                        0
rayonnement_solaire_w_m2     0
temperature_ambiante_c      15
dtype: int64
(17280, 5)
0
```
sites.csv :
```powershell
RangeIndex: 4 entries, 0 to 3
Data columns (total 7 columns):
 #   Column                Non-Null Count  Dtype  
---  ------                --------------  -----  
 0   site_id               4 non-null      str    
 1   nom                   4 non-null      str    
 2   orbite_type           4 non-null      str    
 3   altitude_km           3 non-null      float64
 4   inclination_deg       3 non-null      float64
 5   date_mise_en_service  4 non-null      str    
 6   statut                4 non-null      str    
dtypes: float64(2), str(5)
memory usage: 531.0 bytes
None
site_id                 0
nom                     0
orbite_type             0
altitude_km             1
inclination_deg         1
date_mise_en_service    0
statut                  0
dtype: int64
(4, 7)
0
```
telemetrie.csv :
```powershell
RangeIndex: 635340 entries, 0 to 635339
Data columns (total 7 columns):
 #   Column         Non-Null Count   Dtype  
---  ------         --------------   -----  
 0   timestamp      635340 non-null  str    
 1   equipement_id  635340 non-null  str    
 2   puissance_w    619461 non-null  float64
 3   temperature_c  619455 non-null  float64
 4   rayonnement    635340 non-null  float64
 5   tension_v      619455 non-null  float64
 6   courant_a      619453 non-null  float64
dtypes: float64(5), str(2)
memory usage: 49.1 MB
None
timestamp            0
equipement_id        0
puissance_w      15879
temperature_c    15885
rayonnement          0
tension_v        15885
courant_a        15887
dtype: int64
(635340, 7)
300
```
alarmes.json :
```powershell
alarme_id str
equipement_id str
timestamp datetime64[us]
type_alarme str
severite str
message str
acquittee bool

None
alarme_id        0
equipement_id    1
timestamp        0
type_alarme      0
severite         0
message          0
acquittee        0

(521, 7)

0
```
catalogue.db :
```powershell
TABLE MODELES

RangeIndex: 12 entries, 0 to 11
Data columns (total 7 columns):
 #   Column                Non-Null Count  Dtype  
---  ------                --------------  -----  
 0   modele_id             12 non-null     str    
 1   type_equipement       12 non-null     str    
 2   fabricant             12 non-null     str    
 3   puissance_nominale_w  12 non-null     float64
 4   rendement_nominal     10 non-null     float64
 5   duree_vie_annees      12 non-null     int64  
 6   masse_kg              12 non-null     float64
dtypes: float64(3), int64(1), str(3)
memory usage: 1.2 KB

None
modele_id               0
type_equipement         0
fabricant               0
puissance_nominale_w    0
rendement_nominal       2
duree_vie_annees        0
masse_kg                0
dtype: int64

(12, 7)

0
```
```Powershell
TABLE SEUIL_ALARME

RangeIndex: 6 entries, 0 to 5
Data columns (total 5 columns):
 #   Column          Non-Null Count  Dtype  
---  ------          --------------  -----  
 0   type_alarme     6 non-null      str    
 1   seuil_warning   5 non-null      float64
 2   seuil_critical  5 non-null      float64
 3   unite           5 non-null      str    
 4   description     6 non-null      str    
dtypes: float64(2), str(3)
memory usage: 669.0 bytes

None
type_alarme       0
seuil_warning     1
seuil_critical    1
unite             1
description       0
dtype: int64

(6, 5)

0
```
```powershell
TABLE REFERENT_SITE

RangeIndex: 4 entries, 0 to 3
Data columns (total 4 columns):
 #   Column           Non-Null Count  Dtype  
---  ------           --------------  -----  
 0   site_id          4 non-null      str    
 1   description      3 non-null      str    
 2   capacite_max_kw  3 non-null      float64
 3   zone_orbitale    4 non-null      str    
dtypes: float64(1), str(3)
memory usage: 435.0 bytes

None
site_id            0
description        1
capacite_max_kw    1
zone_orbitale      0
dtype: int64

(4, 4)

0
```
##  Quelles sont les sources disponibles et leur grain ?
- 5 fichier csv 
- 1 fichier JSON
- 1 BDD 

|Sources|Contenu|Grain|
|-------|-------|-----| 
|equipements.csv|~70 équipements|1 ligne par équipement (dimension statique)|
|maintenance.csv|~100 interventions|1 intervention (période date_debut → date_fin)|
|orbite.csv|~17 000 lignes|1 mesure par site toutes les 15 min|
|sites.csv|4 sites|1 ligne par site (dimension statique)|
|telemetrie.csv|~350 000+ lignes|1 mesure par équipement toutes les 5 min|
|alarmes.json|~520 alarmes|1 événement (déclenché à un timestamp donné)|
|modeles.sql|12 modeles|1 ligne par modeles|
|references_sites|4 references|1 ligne par référence|
|seuils_alarmes|6 niveaux|1 ligne par niveau d'alarme|

## Quelles données semblent fiables ou problématiques ?
- **Les données les plus fiables** : équipement, maintenance, modèle, site, seuil_alarme, orbite, alarme.
- **Les données les plus problématiques** :
télémétrie car beaucoup sont non renseignées et beaucoup de doublon.

## Quelles relations peut-on établir entre les sources ?
|sources | relations|
|--------|----------|
|Alarme| Seuil_alarme|
|Site| Références_sites|
|Site| Orbite|
|Equipement|Modeles|
|Equipement| Télémétrie|
|Equipement|Maintenance|
|Equipement|Sites|

## Quelles informations sont nécessaires pour analyser une dégradation de performance ?
Télémétrie, Orbite, Alarme, Seuil_Alarme et Maintenance