import os 
import pandas as pd
import sqlite3
from pathlib import Path

#----------------------------------------------
# CONNEXION BDD
#----------------------------------------------

dossier_script = Path(__file__).resolve().parent

chemin_bdd = dossier_script / "catalogue.db"

print("Base SQLite :", chemin_bdd)

connexion = sqlite3.connect(chemin_bdd)
curseur = connexion.cursor()

#----------------------------------------------
# EXPLORATION CSV 
#----------------------------------------------

root = os.path.dirname(os.path.abspath(__file__))
dossier_data = os.path.join(root, "orbitalis_data_large")

fichier_data_equipement = os.path.join(dossier_data, "equipements.csv")

df_equipement = pd.read_csv(fichier_data_equipement)

print(df_equipement.info())
print(df_equipement.isna().sum())
print(df_equipement.shape)
print(df_equipement.duplicated().sum())

fichier_data_maintenance = os.path.join(dossier_data, "maintenance.csv")

df_maintenance = pd.read_csv(fichier_data_maintenance)

print(df_maintenance.info())
print(df_maintenance.isna().sum())
print(df_maintenance.shape)
print(df_maintenance.duplicated().sum())

fichier_data_orbite = os.path.join(dossier_data, "orbite.csv")

df_orbite = pd.read_csv(fichier_data_orbite)

print(df_orbite.info())
print(df_orbite.isna().sum())
print(df_orbite.shape)
print(df_orbite.duplicated().sum())

fichier_data_sites = os.path.join(dossier_data, "sites.csv")

df_sites = pd.read_csv(fichier_data_sites)

print(df_sites.info())
print(df_sites.isna().sum())
print(df_sites.shape)
print(df_sites.duplicated().sum())

fichier_data_telemetrie = os.path.join(dossier_data, "telemetrie.csv")

df_telemetrie = pd.read_csv(fichier_data_telemetrie)

print(df_telemetrie.info())
print(df_telemetrie.isna().sum())
print(df_telemetrie.shape)
print(df_telemetrie.duplicated().sum())

# ----------------------------------------------
# EXPLORATION BDD
# ----------------------------------------------
def obtenir_infos_donnees():

    connexion = sqlite3.connect(chemin_bdd)

    try:
        # 1. STRUCTURE DE LA TABLE
        df_structure = pd.read_sql_query(
            """
            PRAGMA table_info(references_sites);
            """,
            connexion
        )

        if df_structure.empty:
            print("La table 'references_sites' n'existe pas ou ne contient aucune colonne.")
            return

        colonnes = df_structure["name"].tolist()

        # 2. NOMBRE DE LIGNES
        df_lignes = pd.read_sql_query(
            """
            SELECT COUNT(*) AS nombre_lignes
            FROM references_sites;
            """,
            connexion
        )

        nombre_lignes = df_lignes.loc[0, "nombre_lignes"]


        # 3. NOMBRE DE COLONNES
        nombre_colonnes = len(colonnes)

       
        # 4. VALEURS NULL
        expressions_null = []

        for colonne in colonnes:

            expression = (
                f'SUM(CASE WHEN "{colonne}" IS NULL '
                f'THEN 1 ELSE 0 END) AS "{colonne}"'
            )

            expressions_null.append(expression)

        query_null = f"""
        SELECT
            {", ".join(expressions_null)}
        FROM references_sites;
        """

        df_null = pd.read_sql_query(
            query_null,
            connexion
        )


        # 5. DOUBLONS
        colonnes_doublons = df_structure[
            df_structure["pk"] == 0
        ]["name"].tolist()

        if len(colonnes_doublons) > 0:

            colonnes_sql = ", ".join(
                f'"{colonne}"'
                for colonne in colonnes_doublons
            )

            query_doublons = f"""
            SELECT
                COALESCE(SUM(nombre - 1), 0)
                AS nombre_doublons
            FROM (
                SELECT
                    {colonnes_sql},
                    COUNT(*) AS nombre
                FROM references_sites
                GROUP BY {colonnes_sql}
                HAVING COUNT(*) > 1
            );
            """

            df_doublons = pd.read_sql_query(
                query_doublons,
                connexion
            )

            nombre_doublons = df_doublons.loc[
                0,
                "nombre_doublons"
            ]

        else:
            nombre_doublons = 0


        # AFFICHAGE
        print("\n==============================")
        print("STRUCTURE DE LA TABLE")
        print("==============================")

        print(
            df_structure[
                [
                    "name",
                    "type",
                    "notnull",
                    "pk"
                ]
            ]
        )


        print("\n==============================")
        print("DIMENSIONS")
        print("==============================")

        print(
            f"Nombre de lignes : {nombre_lignes}"
        )

        print(
            f"Nombre de colonnes : {nombre_colonnes}"
        )

        print(
            f"Shape : ({nombre_lignes}, {nombre_colonnes})"
        )


        print("\n==============================")
        print("VALEURS NULL")
        print("==============================")

        print(
            df_null
            .T
            .rename(columns={0: "nombre_null"})
        )


        print("\n==============================")
        print("DOUBLONS")
        print("==============================")

        print(
            f"Nombre de doublons : {nombre_doublons}"
        )

    except sqlite3.Error as erreur:

        print(
            "Erreur SQLite :",
            erreur
        )

    finally:

        connexion.close()


# ----------------------------------------------
# EXECUTION
# ----------------------------------------------

obtenir_infos_donnees()