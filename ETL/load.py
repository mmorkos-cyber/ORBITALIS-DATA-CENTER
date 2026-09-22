from datasets import load_dataset
import sqlite3
from pathlib import Path
import time
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
            type_alarme TEXT,
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
# EXECUTION
# ============================================================
if __name__ == "__main__":
    initialiser_bdd()

# ============================================================
# REQUÊTE D'INSERTION
# ============================================================

def inserer_sites():

    connexion = sqlite3.connect(DB_PATH)
   
    try:
        df_sites = sites_nettoyer(df_sites)
        df_references_sites = ref_sites_nettoyer(df_references_sites)

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

        df_sites_final.to_sql(
            "sites",
            connexion,
            if_exists="append",
            index=False
        )

        connexion.commit()

        print(
            f"{len(df_sites_final)} sites insérés dans la base."
        )


    except (sqlite3.Error, ValueError, KeyError) as erreur:

        print("Erreur lors de l'insertion :", erreur)

        connexion.rollback()


    finally:

        connexion.close()


