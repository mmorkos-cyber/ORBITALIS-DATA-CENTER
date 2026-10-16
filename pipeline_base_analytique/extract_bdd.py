import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DB = BASE_DIR / "data" / "propre" / "orbital_data_center_clean.db"


def get_connexion():
    return sqlite3.connect(SOURCE_DB)


def prepa_dim_orbite(conn):
    return pd.read_sql_query("""
        SELECT orbite_id AS id_orbite, phase,
               rayonnement_solaire_w_m2, temperature_ambiante_c
        FROM phase_orbitale
    """, conn)

def prepa_dim_maintenance(conn):
    return pd.read_sql_query("""
        SELECT maintenance_id AS id_maintenance, date_debut, date_fin,
               type_intervention, cout_eur
        FROM maintenance
    """, conn)

def prepa_dim_alarme(conn):
    return pd.read_sql_query("""
        SELECT a.alarme_id AS id_alarme, a.timestamp AS date_alarme,
               a.severite, a.acquittee,
               sa.type_alarme, sa.seuil_warning, sa.seuil_critical, sa.unite
        FROM alarmes a
        JOIN seuil_alarme sa ON a.id_seuil = sa.id_seuil
    """, conn)

def prepa_dim_equipement(conn):
    return pd.read_sql_query("""
        SELECT e.equipement_id AS id_equipement, m.type_equipement, e.statut,
               e.date_installation, m.puissance_nominale_w, m.rendement_nominal,
               m.duree_vie_annees, m.masse_kg, s.altitude_km
        FROM equipement e
        JOIN modele m ON e.modele_id = m.modele_id
        JOIN sites s  ON e.site_id = s.site_id
    """, conn)


def prepa_dim_temps(conn):
    return pd.read_sql_query(
        "SELECT DISTINCT timestamp FROM mesure_telemetrie",
        conn, parse_dates=["timestamp"])