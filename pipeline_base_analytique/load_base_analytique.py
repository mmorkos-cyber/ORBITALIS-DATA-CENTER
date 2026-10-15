import sqlite3
import os

import numpy as np
from extract_bdd import df_dim_orbite, df_dim_maintenance, df_dim_alarme, df_dim_equipement, df_dim_temps, df_fait_production
import pandas as pd


dossier_pipeline = os.path.dirname(os.path.abspath(__file__))
fichier_base_analytique = os.path.join(dossier_pipeline, "base_analytique.db")

conn = sqlite3.connect(fichier_base_analytique)

def init_base_analytique():

    cursor = conn.cursor()

    try:
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS dim_orbite (
                    orbite_id INTEGER PRIMARY KEY,
                    phase TEXT,
                    rayonnement_solaire_w_m2 REAL,
                    temperature_ambiante_c REAL
                );
                """)

        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dim_maintenance (
                            maintenance_id TEXT PRIMARY KEY,
                            date_debut DATETIME,
                            date_fin DATETIME,
                            type_intervention TEXT
                        );
                        """)

        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dim_alarme (
                            alarme_id TEXT PRIMARY KEY,
                            severite TEXT,
                            acquittee INTEGER,
                            type_alarme TEXT,
                            seuil_warning REAL,
                            seuil_critical REAL,
                            unite TEXT
                        );
                        """)

        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dim_equipement (
                            equipement_id TEXT PRIMARY KEY,
                            statut TEXT,
                            date_installation DATETIME,
                            type_equipement TEXT,
                            masse_kg REAL,
                            duree_vie_annees INTEGER,
                            duree_vie_restante INTEGER,
                            altitude_km REAL
                        );
                        """)

        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dim_temps (
                            id_temps TEXT PRIMARY KEY,
                            date DATETIME,
                            annee INTEGER,
                            mois INTEGER,
                            jour INTEGER,
                            heure INTEGER,
                            minute INTEGER
                        );
                        """)

        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS fait_production (
                            id_production TEXT PRIMARY KEY,
                            equipement_id TEXT,
                            id_temps TEXT,
                            orbite_id INTEGER,
                            maintenance_id TEXT,
                            alarme_id TEXT,
                            puissance_w REAL,
                            temperature_c REAL,
                            rayonnement REAL,
                            tension_v REAL,
                            courant_a REAL,
                            puissance_nominale_w REAL,
                            rendement_nominal REAL,
                            performance REAL,
                            perte_production REAL,
                    
                            FOREIGN KEY (equipement_id) REFERENCES dim_equipement(equipement_id),
                            FOREIGN KEY (id_temps) REFERENCES dim_temps(id_temps),
                            FOREIGN KEY (orbite_id) REFERENCES dim_orbite(orbite_id),
                            FOREIGN KEY (maintenance_id) REFERENCES dim_maintenance(maintenance_id),
                            FOREIGN KEY (alarme_id) REFERENCES dim_alarme(alarme_id)
                        );
                    """)

        conn.commit()

    except sqlite3.Error as erreur:
            print("Erreur SQLite :", erreur)
            conn.rollback()
    
    


def insert_orbite():
    df_dim_orbite.to_sql("dim_orbite", conn, if_exists="append", index=False)

def insert_maintenance():
    df_dim_maintenance.to_sql("dim_maintenance", conn, if_exists="append", index=False)

def insert_alarme():
    df_dim_alarme.to_sql("dim_alarme", conn, if_exists="append", index=False)

def insert_equipement():

    df_dim_equipement['date_fin_theorique'] = df_dim_equipement['date_installation'] + pd.to_timedelta(df_dim_equipement['duree_vie_annees'] * 365.25, unit='D')

    date_actuelle = pd.Timestamp.now()
    df_dim_equipement['duree_vie_restante'] = (df_dim_equipement['date_fin_theorique'] - date_actuelle).dt.days
    df_dim_equipement = df_dim_equipement.drop(columns=['date_fin_theorique'])

    df_dim_equipement.to_sql("dim_equipement", conn, if_exists="append", index=False)

def insert_temps():
    df_dim_temps = pd.DataFrame({'timestamp': df_dim_temps['timestamp'].unique()})
    df_dim_temps['id_temps'] = df_dim_temps['timestamp'].dt.strftime('%Y%m%d%H%M%S').astype('int64')
    df_dim_temps['date'] = df_dim_temps['timestamp']
    df_dim_temps['annee'] = pd.DatetimeIndex(df_dim_temps['timestamp']).year
    df_dim_temps['mois'] = pd.DatetimeIndex(df_dim_temps['timestamp']).month
    df_dim_temps['jour'] = pd.DatetimeIndex(df_dim_temps['timestamp']).day
    df_dim_temps['heure'] = pd.DatetimeIndex(df_dim_temps['timestamp']).hour
    df_dim_temps['minute'] = pd.DatetimeIndex(df_dim_temps['timestamp']).minute
    df_dim_temps = df_dim_temps.drop(columns=['timestamp'])

    df_dim_temps.to_sql("dim_temps", conn, if_exists="append", index=False)

def insert_production():
    df_fait_production['id_temps'] = df_fait_production['timestamp'].dt.strftime('%Y%m%d%H%M%S').astype('int64')

    df_fait_production['performance'] = df_fait_production['puissance_w'] / df_fait_production['puissance_nominale_w']

    df_fait_production = df_fait_production.sort_values(['equipement_id', 'timestamp'])
    df_fait_production['production_precedente'] = df_fait_production.groupby('equipement_id')['puissance_w'].shift(1)
    diff = df_fait_production['puissance_w'] - df_fait_production['production_precedente']
    df_fait_production['perte_production'] = np.where(diff < 0, df_fait_production['production_precedente'] - df_fait_production['puissance_w'], 0)

    df_fait_production = df_fait_production.drop(columns=['timestamp', 'production_precedente'])

    df_fait_production.to_sql("fait_production", conn, if_exists="append", index=False)


if __name__ == "__main__":
    init_base_analytique()
    insert_orbite()
    insert_maintenance()
    insert_alarme()
    insert_equipement()
    insert_temps()
    insert_production()
    conn.close()