import os
import sqlite3
import pandas as pd

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fichier_bdd = os.path.join(root, "ETL", "orbital_data_center_clean.db")

conn = sqlite3.connect(fichier_bdd)

query_site = """
    SELECT
        si.site_id,
        si.nom,
        si.orbite_type,
        si.altitude_km,
        si.inclination_deg,
        si.date_mise_en_service,
        si.statut,
        si.description,
        si.capacite_max_kw,
        si.zone_orbitale
    FROM sites si
"""

df_dim_site = pd.read_sql_query(query_site, conn)

query_alarme = """
    SELECT
        sa.id_seuil,
        sa.type_alarme,
        sa.seuil_warning,
        sa.seuil_critical,
        sa.unite,
        sa.description
    FROM seuil_alarme sa
"""

df_dim_alarme = pd.read_sql_query(query_alarme, conn)

query_equipement = """
    SELECT
        e.equipement_id,
        e.statut,
        e.date_installation,
    FROM equipement e
"""

df_dim_equipement = pd.read_sql_query(query_equipement, conn)

query_modele = """
    SELECT
        mo.modele_id,
        mo.type_equipement,
        mo.rendement_nominal,
        mo.duree_vie_annees,
        mo.masse_kg
    FROM modele mo
"""

df_dim_modele = pd.read_sql_query(query_modele, conn)

query_temps = """
    SELECT
        me.timestamp
    FROM mesure_telemetrie me
"""

df_dim_temps = pd.read_sql_query(query_temps, conn)

query_telemetrie = """
    SELECT
        mt.timestamp,
        mt.equipement_id,
        e.site_id,
        mt.puissance_w,
        mt.temperature_c,
        mt.rayonnement,
        mt.tension_v,
        mt.courant_a,
        mo.puissance_nominale_w,
        mo.rendement_nominal,
        po.phase,
        po.rayonnement_solaire_w_m2,
        po.temperature_ambiante_c,
        ma.maintenance_id,
        a.severite
    FROM mesure_telemetrie mt
    JOIN equipement e ON mt.equipement_id = e.equipement_id
    JOIN sites si ON si.site_id = e.site_id
    JOIN phase_orbitale po ON si.site_id = po.site_id
    JOIN modele mo ON e.modele_id = mo.modele_id
    JOIN maintenance ma ON  e.equipement_id = ma.equipement_id
    JOIN alarmes a ON e.equipement_id = a.equipement_id
"""

df_fait_telemetrie = pd.read_sql_query(query_telemetrie, conn)

conn.close()