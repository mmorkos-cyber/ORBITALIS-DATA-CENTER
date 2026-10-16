import sqlite3
import time
from pathlib import Path
import extract_bdd as ex

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_CLEAN = BASE_DIR / "data" / "propre" / "base_analytique.db"


SQL_SCHEMA = """
CREATE TABLE dim_orbite (
    id_orbite INTEGER PRIMARY KEY,
    phase TEXT,
    rayonnement_solaire_w_m2 REAL,
    temperature_ambiante_c REAL
);
CREATE TABLE dim_maintenance (
    id_maintenance TEXT PRIMARY KEY,
    date_debut DATETIME, date_fin DATETIME,
    type_intervention TEXT, cout_eur REAL
);
CREATE TABLE dim_alarme (
    id_alarme TEXT PRIMARY KEY,
    date_alarme DATETIME, severite TEXT, acquittee INTEGER,
    type_alarme TEXT, seuil_warning REAL, seuil_critical REAL, unite TEXT
);
CREATE TABLE dim_equipement (
    id_equipement TEXT PRIMARY KEY,
    type_equipement TEXT, statut TEXT, date_installation DATETIME,
    puissance_nominale_w REAL, rendement_nominal REAL,
    duree_vie_annees INTEGER, masse_kg REAL, altitude_km REAL
);
CREATE TABLE dim_temps (
    id_temps TEXT PRIMARY KEY,
    date DATETIME, annee INTEGER, mois INTEGER,
    jour INTEGER, heure INTEGER, minute INTEGER
);
CREATE TABLE fait_production (
    id_production INTEGER PRIMARY KEY,
    id_equipement TEXT, id_temps TEXT, id_orbite INTEGER,
    id_maintenance TEXT, id_alarme TEXT,
    puissance_w REAL, puissance_nominale_w REAL, rayonnement REAL,
    courant_a REAL, tension_v REAL, temperature_c REAL,
    performance REAL, perte_production_w REAL, perte_energie_kwh REAL,
    FOREIGN KEY (id_equipement)  REFERENCES dim_equipement(id_equipement),
    FOREIGN KEY (id_temps)       REFERENCES dim_temps(id_temps),
    FOREIGN KEY (id_orbite)      REFERENCES dim_orbite(id_orbite),
    FOREIGN KEY (id_maintenance) REFERENCES dim_maintenance(id_maintenance),
    FOREIGN KEY (id_alarme)      REFERENCES dim_alarme(id_alarme)
);
"""

SQL_FAIT_PRODUCTION = f"""
ATTACH DATABASE '{ex.SOURCE_DB}' AS src;
PRAGMA main.journal_mode = OFF;
PRAGMA main.synchronous = OFF;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -500000;

-- Alarms: one row per (equipment, timestamp), indexed
CREATE TEMP TABLE t_alarme AS
SELECT equipement_id, timestamp, MIN(alarme_id) AS id_alarme
FROM src.alarmes
GROUP BY equipement_id, timestamp;
CREATE INDEX ix_t_alarme ON t_alarme(equipement_id, timestamp);

-- Orbits: one row per (site, timestamp), indexed
CREATE TEMP TABLE t_orbite AS
SELECT site_id, timestamp, MIN(orbite_id) AS id_orbite
FROM src.phase_orbitale
GROUP BY site_id, timestamp;
CREATE INDEX ix_t_orbite ON t_orbite(site_id, timestamp);

-- Maintenance: indexed copy
CREATE TEMP TABLE t_maint AS
SELECT equipement_id, date_debut, date_fin, maintenance_id
FROM src.maintenance;
CREATE INDEX ix_t_maint ON t_maint(equipement_id, date_debut);

INSERT INTO fait_production (
    id_production, id_equipement, id_temps, id_orbite, id_maintenance, id_alarme,
    puissance_w, puissance_nominale_w, rayonnement, courant_a, tension_v, temperature_c,
    performance, perte_production_w, perte_energie_kwh
)
WITH base AS (
    SELECT
        mt.mesure_id     AS id_production,
        mt.equipement_id AS id_equipement,
        mt.timestamp     AS ts,
        o.id_orbite,
        (SELECT m.maintenance_id FROM t_maint m
          WHERE m.equipement_id = mt.equipement_id
            AND mt.timestamp BETWEEN m.date_debut AND m.date_fin
          LIMIT 1)       AS id_maintenance,
        a.id_alarme,
        mt.puissance_w, mo.puissance_nominale_w, mt.rayonnement,
        mt.courant_a, mt.tension_v, mt.temperature_c
    FROM src.mesure_telemetrie mt
    JOIN src.equipement e ON e.equipement_id = mt.equipement_id
    JOIN src.modele mo    ON mo.modele_id = e.modele_id
    LEFT JOIN t_orbite o  ON o.site_id = e.site_id
                         AND o.timestamp = mt.timestamp
    LEFT JOIN t_alarme a  ON a.equipement_id = mt.equipement_id
                         AND a.timestamp = mt.timestamp
),
avec_precedente AS (
    SELECT *,
           LAG(puissance_w) OVER (PARTITION BY id_equipement ORDER BY ts) AS precedente
    FROM base
)
SELECT
    id_production, id_equipement,
    strftime('%Y%m%d%H%M%S', ts),
    id_orbite, id_maintenance, id_alarme,
    puissance_w, puissance_nominale_w, rayonnement, courant_a, tension_v, temperature_c,
    puissance_w / puissance_nominale_w,
    MAX(COALESCE(precedente - puissance_w, 0), 0),
    MAX(COALESCE(precedente - puissance_w, 0), 0) * 5.0 / 60 / 1000
FROM avec_precedente;
"""


def init_base_analytique(conn_dst):
    conn_dst.executescript(SQL_SCHEMA)


def insert_dimension(df, nom_table, conn_dst):
    df.to_sql(nom_table, conn_dst, if_exists="append", index=False)


def insert_temps(conn_src, conn_dst):
    df = ex.prepa_dim_temps(conn_src)
    df["id_temps"] = df["timestamp"].dt.strftime("%Y%m%d%H%M%S")
    df["date"] = df["timestamp"]
    df["annee"] = df["timestamp"].dt.year
    df["mois"] = df["timestamp"].dt.month
    df["jour"] = df["timestamp"].dt.day
    df["heure"] = df["timestamp"].dt.hour
    df["minute"] = df["timestamp"].dt.minute
    insert_dimension(df.drop(columns="timestamp"), "dim_temps", conn_dst)


def insert_production(conn_dst):
    debut = time.time()
    conn_dst.executescript(SQL_FAIT_PRODUCTION)
    conn_dst.commit()
    print(f"chargé en {time.time() - debut:.0f} s")


if __name__ == "__main__":
    DATA_CLEAN.unlink(missing_ok=True)

    conn_src = ex.get_connexion()
    conn_dst = sqlite3.connect(DATA_CLEAN)

    print("1 - création des tables");  init_base_analytique(conn_dst)
    print("2 - dim_orbite");           insert_dimension(ex.prepa_dim_orbite(conn_src), "dim_orbite", conn_dst)
    print("3 - dim_maintenance");      insert_dimension(ex.prepa_dim_maintenance(conn_src), "dim_maintenance", conn_dst)
    print("4 - dim_alarme");           insert_dimension(ex.prepa_dim_alarme(conn_src), "dim_alarme", conn_dst)
    print("5 - dim_equipement");       insert_dimension(ex.prepa_dim_equipement(conn_src), "dim_equipement", conn_dst)
    print("6 - dim_temps");            insert_temps(conn_src, conn_dst)
    print("7 - fait_production");      insert_production(conn_dst)

    conn_src.close()
    conn_dst.close()