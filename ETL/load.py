from datasets import load_dataset
import sqlite3
from pathlib import Path
import time
import pandas as pd
from transform import df_alarmes, df_equipement, df_maintenance, df_orbite, df_sites, df_telemetrie, df_modeles, df_seuils_alarmes, df_references_sites

# ============================================================
# CONFIGURATION
# ============================================================

DOSSIER_SCRIPT = Path(__file__).resolve().parent
DB_PATH = DOSSIER_SCRIPT / "orbital_data_center_clean.db"

# ============================================================
# CONNEXION SQLITE
# ============================================================

connexion = sqlite3.connect(DB_PATH)
curseur = connexion.cursor()

# ============================================================
# CRÉATION DES TABLES
# ============================================================

def initialiser_bdd():
    connexion = sqlite3.connect(DB_PATH)
    
    try:
        curseur = connexion.cursor()
    
        # Active les clés étrangères dans SQLite
        curseur.execute("PRAGMA foreign_keys = ON;")
    
    
        # ------------------------------------------------
        # TABLE SITES
        # ------------------------------------------------ 
        curseur.execute("""
                CREATE TABLE IF NOT EXISTS sites (
                    site_id TEXT PRIMARY KEY,
                    nom TEXT,
                    orbite_type TEXT,
                    altitude_km REAL,
                    inclination_deg REAL,
                    date_mise_en_service TEXT,
                    statut TEXT,
                    description TEXT,
                    capacite_max_kw REAL,
                    zone_orbitale TEXT
                );
                """)

        # ------------------------------------------------
        # TABLE MODELE
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS modele (
            modele_id TEXT PRIMARY KEY,
            type_equipement TEXT,
            fabricant TEXT,
            puissance_nominale_w REAL,
            rendement_nominal REAL,
            duree_vie_annees INTEGER,
            masse_kg REAL
        );
        """)

        # ------------------------------------------------
        # TABLE SEUIL_ALARME
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS seuil_alarme (
            id_seuil INTEGER PRIMARY KEY AUTOINCREMENT,
            type_alarme
            seuil_warning REAL,
            seuil_critical REAL,
            unite TEXT,
            description TEXT
        );
        """)

        # ------------------------------------------------
        # TABLE EQUIPEMENT
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS equipement (
            equipement_id TEXT PRIMARY KEY,
            date_installation TEXT,
            statut TEXT,
            site_id TEXT,
            modele_id TEXT,

            FOREIGN KEY (site_id)
                REFERENCES sites(site_id),

            FOREIGN KEY (modele_id)
                REFERENCES modele(modele_id)
        );
        """)


        # ------------------------------------------------
        # TABLE MAINTENANCE
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance (
            maintenance_id TEXT PRIMARY KEY,
            date_debut TEXT,
            date_fin TEXT,
            type_intervention TEXT,
            technicien TEXT,
            cout_eur INTEGER,
            commentaire TEXT,
            equipement_id TEXT,

            FOREIGN KEY (equipement_id)
                REFERENCES equipement(equipement_id)
        );
        """)


        # ------------------------------------------------
        # TABLE PHASE_ORBITALE
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS phase_orbitale (
            orbite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ TEXT,
            phase TEXT,
            rayonnement_solaire_w_m2 REAL,
            temperature_ambiante_c REAL,
            site_id TEXT,

            FOREIGN KEY (site_id)
                REFERENCES sites(site_id)
        );
        """)


        # ------------------------------------------------
        # TABLE MESURE_TELEMETRIE
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS mesure_telemetrie (
            mesure_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ TEXT,
            puissance_w REAL,
            temperature_c REAL,
            rayonnement REAL,
            tension_v REAL,
            courant_a REAL,
            equipement_id TEXT,

            FOREIGN KEY (equipement_id)
                REFERENCES equipement(equipement_id)
        );
        """)


        # ------------------------------------------------
        # TABLE ALARMES
        # ------------------------------------------------
        curseur.execute("""
        CREATE TABLE IF NOT EXISTS alarmes (
            alarme_id TEXT PRIMARY KEY,
            timestamp_ TEXT,
            severite TEXT,
            message TEXT,
            acquittee INTEGER
                CHECK (acquittee IN (0, 1)),
            id_seuil TEXT,
            equipement_id TEXT,

            FOREIGN KEY (id_seuil)
                REFERENCES seuil_alarme(id_seuil),

            FOREIGN KEY (equipement_id)
                REFERENCES equipement(equipement_id)
        );
        """)


        # ------------------------------------------------
        # VALIDATION
        # ------------------------------------------------
        connexion.commit()

        print("Base de données initialisée avec succès.")

    except sqlite3.Error as erreur:
        print("Erreur SQLite :", erreur)
        connexion.rollback()

    finally:
        connexion.close()


# ============================================================
# INSERTION DE LA TABLE SITES
# ============================================================
def inserer_sites():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        sites = df_sites.copy()
        references = df_references_sites.copy()

# Fusion des id
        df_sites_final = sites.merge(
            references,
            on="site_id",
            how="left"
        )
# Insertion des données récupérées
        df_sites_final = df_sites_final[
            [
                "site_id",
                "nom",
                "orbite_type",
                "altitude_km",
                "inclination_deg",
                "date_mise_en_service",
                "statut",
                "description",
                "capacite_max_kw",
                "zone_orbitale"
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_sites_final.head())

        print(f"Nombre de sites : {len(df_sites_final)}")

        df_sites_final.to_sql(
            "sites",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_sites_final)} lignes insérées dans la table sites.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion des sites :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE MODELE
# ============================================================
def inserer_modele():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        modele = df_modeles.copy()

# Insertion des données récupérées
        df_modele_final = modele[
            [
            "modele_id",
            "type_equipement",
            "fabricant",
            "puissance_nominale_w",
            "rendement_nominal",
            "duree_vie_annees",
            "masse_kg"
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_modele_final.head())

        print(f"Nombre de modele : {len(df_modele_final)}")

        df_modele_final.to_sql(
            "modele",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_modele_final)} lignes insérées dans la table modele.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion des modèles :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE SEUIL_ALARME
# ============================================================

def inserer_seuil_alarme():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        seuils_alarmes = df_seuils_alarmes.copy()

# Insertion des données récupérées
        df_seuil_alarme_final = seuils_alarmes[
            [
            "type_alarme",
            "seuil_warning",
            "seuil_critical",
            "unite",
            "description"
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_seuil_alarme_final.head())

        print(f"Nombre de seuil d'alarme : {len(df_seuil_alarme_final)}")

        df_seuil_alarme_final.to_sql(
            "seuil_alarme",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_seuil_alarme_final)} lignes insérées dans la table seuil_alarme.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion des seuil_alarme :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE EQUIPEMENT
# ============================================================

def inserer_equipement():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        equipement = df_equipement.copy()

# On récupère modele_id grâce à la colonne "modele"
        equipement.rename(
            columns={"modele": "modele_id"},
            inplace=True
        )
    
# Insertion des données récupérées
        df_equipement_final = equipement[
            [
            "equipement_id",
            "date_installation",
            "statut",
            "site_id"
            "modele_id"
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_equipement_final.head())

        print(f"Nombre d'équipement : {len(df_equipement_final)}")

        df_equipement_final.to_sql(
            "equipement",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_equipement_final)} lignes insérées dans la table equipement.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion des equipements :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE MAINTENANCE
# ============================================================

def inserer_maintenance():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        maintenance = df_maintenance.copy()

# Insertion des données récupérées
        df_maintenance_final = maintenance[
            [
            "maintenance_id",
            "date_debut",
            "date_fin",
            "type_intervention",
            "technicien",
            "cout_eur",
            "commentaire",
            "equipement_id",
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_maintenance_final.head())

        print(f"Nombre de ligne : {len(df_maintenance_final)}")

        df_maintenance_final.to_sql(
            "maintenance",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_maintenance_final)} lignes insérées dans la table maintenance.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion de la maintenance :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE PHASE_ORBITALE
# ============================================================

def inserer_phase_orbitale():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        orbite = df_orbite.copy()
    
# Insertion des données récupérées
        df_orbite_final = orbite[
            [
            "timestamp_",
            "phase",
            "rayonnement_solaire_w_m2",
            "temperature_ambiante_c",
            "site_id",
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_orbite_final.head())

        print(f"Nombre de ligne : {len(df_orbite_final)}")

        df_orbite_final.to_sql(
            "phase_orbitale",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_orbite_final)} lignes insérées dans la table phase_orbitale.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion de la phase_orbitale :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE MESURE_TELEMETRIE
# ============================================================

def inserer_mesure_telemetrie():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        telemetrie = df_telemetrie.copy()
    
# Insertion des données récupérées
        df_telemetrie_final = telemetrie[
            [
            "timestamp_",
            "puissance_w",
            "temperature_c",
            "rayonnement",
            "tension_v",
            "courant_a",
            "equipement_id",
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_telemetrie_final.head())

        print(f"Nombre de ligne : {len(df_telemetrie_final)}")

        df_telemetrie_final.to_sql(
            "mesure_telemetrie",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_telemetrie_final)} lignes insérées dans la table mesure_telemetrie.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion de la mesure_telemetrie :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# INSERTION DE LA TABLE ALARMES
# ============================================================

def inserer_alarmes():

    connexion = sqlite3.connect(DB_PATH)

    try:
# recupération des éléments du dataframe
        alarmes = df_alarmes.copy()

# On récupère id_seuil
        df_seuils_bdd = pd.read_sql_query(
            """
            SELECT
                id_seuil,
                type_alarme
            FROM seuil_alarme
            """,
            connexion
        )

        alarmes = alarmes.merge(
            df_seuils_bdd,
            on="type_alarme",
            how="left"
        )
    
# Insertion des données récupérées
        df_alarmes_final = alarmes[
            [
            "alarme_id",
            "timestamp_",
            "severite",
            "message",
            "acquittee",
            "id_seuil",
            "equipement_id"
            ]
        ]
# Vérification
        print("Données qui vont être insérées :")
        print(df_alarmes_final.head())

        print(f"Nombre de ligne : {len(df_alarmes_final)}")

        df_alarmes_final.to_sql(
            "alarmes",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(f"{len(df_alarmes_final)} lignes insérées dans la table alarme.")

    except (sqlite3.Error, KeyError, ValueError) as erreur:

        print("Erreur lors de l'insertion de la alarme :",erreur)

        connexion.rollback()

    finally:

        connexion.close()

# ============================================================
# EXECUTION
# ============================================================
if __name__ == "__main__":
    initialiser_bdd()

    inserer_sites()
    inserer_modele()
    inserer_seuil_alarme()
    inserer_equipement()
    inserer_maintenance()
    inserer_phase_orbitale()
    inserer_mesure_telemetrie()
    inserer_alarmes()