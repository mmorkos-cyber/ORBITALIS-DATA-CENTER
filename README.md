# ORBITALIS-DATA-CENTER

## REQUETE SQL : 
Quelle est la production totale par équipement et par jour ?
```SQL
SELECT
    equipement_id,
    DATE(timestamp) AS jour,
    SUM(puissance_w) AS production_totale_w
FROM mesure_telemetrie
GROUP BY
    equipement_id,
    DATE(timestamp)
ORDER BY
    jour,
    equipement_id;
```
Quels équipements présentent les performances moyennes les plus faibles (hors périodes d’éclipse) ?
```SQL

```
Combien d’alarmes chaque équipement a-t-il générées, par niveau de sévérité ?
Quel est le délai moyen entre deux opérations de maintenance pour un même équipement ?
Quels équipements n’ont pas été maintenus depuis plus de 90 jours ?
Quelle est la perte de production estimée par site (en kWh) ?
Comment évolue la performance d’un équipement au cours du temps ? (utiliser au moins une fonction de fenêtre)
Comparer les performances pendant les phases d’ensoleillement et les phases d’éclipse sans considérer l’éclipse comme une panne.
(Question business) Quel est le coût estimé des pertes de production non anticipées sur la période disponible ?