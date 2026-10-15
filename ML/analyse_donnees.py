import sqlite3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#=====================================================
# 1. CHARGEMENT DES DONNEES
#=====================================================
def charger_donnees_analytiques(chemin_bdd):

    chemin_bdd = Path(chemin_bdd)

    if not chemin_bdd.is_file():
        raise FileNotFoundError(f"Base analytique introuvable : {chemin_bdd}")

    with sqlite3.connect(chemin_bdd) as connexion:

        df = pd.read_sql_query(
            """
            SELECT
                f.id_production,
                f.id_equipement,
                t.date,
                t.annee,
                t.mois,
                t.jour,
                t.heure,
                t.minute,

                e.type_equipement,
                e.statut,
                e.date_installation,
                e.puissance_nominal_w,
                e.rendement_nomminal,
                e.duree_vie_annee,
                e.masse_kg,
                e.altitude_km,

                o.phase,
                o.rayonnement_solaire_w_m2,
                o.temperature_ambiante_c,

                f.puissance_w,
                f.rayonnement,
                f.courant_a,
                f.tension_v,
                f.temperature_c,
                f.performance,
                f.perte_production_w,
                f.perte_energie_kwh

            FROM FAIT_PRODUCTION f

            JOIN DIM_TEMPS t
                ON f.id_temps = t.id_temps

            JOIN DIM_EQUIPEMENT e
                ON f.id_equipement = e.id_equipement

            LEFT JOIN DIM_ORBITE o
                ON f.id_orbite = o.id_orbite
            """,
            connexion
        )

    return df

#=====================================================
# 2.PREPARATION DU DATAFRAME ML
#=====================================================

def preparer_dataframe_ml(df, df_alarmes, df_maintenance):
    df = df.copy()

    verifier_colonnes_ml(df)

    df["date"] = pd.to_datetime(
        df["date"], utc=True, errors="coerce"
    )

    df = df.dropna(subset=["date", "id_equipement"])
    df = df.sort_values(["id_equipement", "date"])

    df = creer_features_equipement(df)
    df = creer_features_telemetrie(df)
    df = creer_features_orbite(df)
    df = creer_features_alarmes(df, df_alarmes)
    df = creer_features_maintenance(df, df_maintenance)

    return df


def verifier_colonnes_ml(df):

    colonnes_attendues = [
        # Identifiants et temporalité
        "id_production",
        "id_equipement",
        "date",
        "annee",
        "mois",
        "jour",
        "heure",
        "minute",

        # Equipements
        "type_equipement",
        "statut",
        "date_installation",
        "puissance_nominal_w",
        "rendement_nomminal",
        "duree_vie_annee",
        "masse_kg",
        "altitude_km",

        # Contexte orbital
        "phase",
        "rayonnement_solaire_w_m2",
        "temperature_ambiante_c",

        # Télémétrie et indicateurs
        "puissance_w",
        "rayonnement",
        "courant_a",
        "tension_v",
        "temperature_c",
        "performance",
        "perte_production_w",
        "perte_energie_kwh"
    ]

    colonnes_manquantes = [
        colonne
        for colonne in colonnes_attendues
        if colonne not in df.columns
    ]

    if colonnes_manquantes:
        raise ValueError(f"Colonnes manquantes : {colonnes_manquantes}")

    print("Toutes les colonnes nécessaires sont présentes.")

#=====================================================
# 3. CREATION DES FEATURES
#=====================================================

# Création des features pour l'équipement:
def creer_features_equipement(df):
    df = df.copy()

    df["date_installation"] = pd.to_datetime(df["date_installation"], utc=True, errors="coerce")
    df["age_equipement_annees"] = ((df["date"] - df["date_installation"]).dt.total_seconds() / (365.25 * 24 * 3600))
    df["duree_vie_restante"] = (df["duree_vie_annee"] - df["age_equipement_annees"]).clip(lower=0)
    df["part_duree_vie_utilisee"] = (df["age_equipement_annees"] / df["duree_vie_annee"].replace(0, float("nan")))

    return df

# Création des features pour la télémétrie :
def creer_features_telemetrie(df):
    df = df.copy()
    df = df.sort_values(["id_equipement", "date_"])

    def calculer_historiques(groupe):
        groupe = groupe.copy()
        groupe = groupe.set_index("date_")

        # Variables et statistiques à calculer (moyenne et écart_type qui peuvent indiqué un disfonctionnement)
        variables = {
            "performance": ["mean", "std"],
            "puissance_w": ["mean", "std"],
            "temperature_c": ["mean", "max", "std"],
            "tension_v": ["mean", "std"],
            "courant_a": ["mean", "std"],
            "rayonnement": ["mean", "max"]
        }

        for colonne, statistiques in variables.items():
            for duree in ["1h", "6h", "24h"]:
                historique = groupe[colonne].rolling(duree,min_periods=3)

                for statistique in statistiques:
                    nom_feature = (f"{colonne}_{statistique}_{duree}")

                    groupe[nom_feature] = getattr(historique, statistique)()

        # Écart de la valeur actuelle avec les mesures
        # précédentes de la dernière heure
        for colonne in [
            "performance",
            "puissance_w",
            "temperature_c",
            "tension_v",
            "courant_a"
        ]:
            moyenne_precedente = groupe[colonne].rolling("1h",closed="left",min_periods=3).mean()

            groupe[f"{colonne}_ecart_moyenne_1h"] = (groupe[colonne] - moyenne_precedente)

        return groupe.reset_index()

    groupes = [
        calculer_historiques(groupe)
        for _, groupe in df.groupby("id_equipement")
    ]

    return pd.concat(groupes, ignore_index=True)

# Création des features liées à l'orbite
def creer_features_orbite(df):
    df = df.copy()
    df = df.sort_values(["id_equipement", "date"])

# Voir les écarts de températures anormale qui peuvent être signe de disfonctionnement
    df["ecart_temperature"] = (df["temperature_c"] - df["temperature_ambiante_c"])

    def calculer_orbite(groupe):
        groupe = groupe.copy()
        groupe = groupe.set_index("date")

        variables = [
            "rayonnement_solaire_w_m2",
            "temperature_ambiante_c",
            "ecart_temperature"
        ]

        for colonne in variables:
            for duree in ["1h", "6h", "24h"]:
                historique = groupe[colonne].rolling(duree, min_periods=3)

                groupe[f"{colonne}_moyenne_{duree}"] = (historique.mean())
                groupe[f"{colonne}_max_{duree}"] = (historique.max())
                groupe[f"{colonne}_std_{duree}"] = (historique.std())

        # Variations par rapport à l'historique antérieur
        for colonne in [
            "rayonnement_solaire_w_m2",
            "temperature_ambiante_c"
        ]:
            historique_precedent = groupe[colonne].rolling("1h",closed="left", min_periods=3).mean()

            groupe[f"{colonne}_ecart_moyenne_1h"] = (groupe[colonne] - historique_precedent)

        return groupe.reset_index()

    groupes = [
        calculer_orbite(groupe)
        for _, groupe in df.groupby("id_equipement")
    ]

    return pd.concat(groupes, ignore_index=True)

#Création des features liées à l'alarme
def creer_features_alarmes(df, df_alarmes):

    df = df.copy()
    df_alarmes = df_alarmes.copy()

    # Conversion des dates
    df_alarmes["date_alarme"] = pd.to_datetime(df_alarmes["date_alarme"], utc=True)

    # Création des nouvelles colonnes
    df["nb_alarmes_1h"] = 0
    df["nb_alarmes_6h"] = 0
    df["nb_alarmes_24h"] = 0

    df["nb_warning_24h"] = 0
    df["nb_critical_24h"] = 0

    df["nb_alarmes_puissance_24h"] = 0
    df["nb_alarmes_temperature_24h"] = 0

    df["heures_depuis_derniere_alarme"] = float("nan")

    # Parcours des équipements
    for id_equipement, groupe in df.groupby("id_equipement"):

        # Récupération des alarmes de cet équipement
        alarmes_equipement = df_alarmes[df_alarmes["id_equipement"] == id_equipement]

        # Parcours des observations
        for index, ligne in groupe.iterrows():

            date = ligne["date"]

            # Alarmes des dernières 24 heures
            alarmes_24h = alarmes_equipement[
                (alarmes_equipement["date_alarme"] <= date) &
                (alarmes_equipement["date_alarme"] > date - pd.Timedelta(hours=24))
            ]

            # Alarmes des dernières 6 heures
            alarmes_6h = alarmes_24h[alarmes_24h["date_alarme"] > date - pd.Timedelta(hours=6)]

            # Alarmes de la dernière heure
            alarmes_1h = alarmes_6h[alarmes_6h["date_alarme"] > date - pd.Timedelta(hours=1)]

            # Comptage des alarmes
            df.loc[index, "nb_alarmes_1h"] = len(alarmes_1h)
            df.loc[index, "nb_alarmes_6h"] = len(alarmes_6h)
            df.loc[index, "nb_alarmes_24h"] = len(alarmes_24h)

            # Alarmes selon leur sévérité
            df.loc[index, "nb_warning_24h"] = (alarmes_24h["severite"] == "warning").sum()
            df.loc[index, "nb_critical_24h"] = (alarmes_24h["severite"] == "critical").sum()

            # Alarmes liées à la puissance
            df.loc[index, "nb_alarmes_puissance_24h"] = (alarmes_24h["type_alarme"].isin(["perte_puissance", "surcharge"])).sum()

            # Alarmes liées à la température
            df.loc[index, "nb_alarmes_temperature_24h"] = (alarmes_24h["type_alarme"] == "surchauffe").sum()

            # Recherche de la dernière alarme connue
            alarmes_passees = alarmes_equipement[alarmes_equipement["date_alarme"] <= date]

            if not alarmes_passees.empty:

                derniere_alarme = alarmes_passees["date_alarme"].max()

                df.loc[index, "heures_depuis_derniere_alarme"] = ((date - derniere_alarme).total_seconds() / 3600)

    return df

# Création des features liées à la maintenance
def creer_features_maintenance(df, df_maintenance):

    df = df.copy()
    df_maintenance = df_maintenance.copy()

    # Conversion des dates
    df_maintenance["date_fin"] = pd.to_datetime(df_maintenance["date_fin"], utc=True)

    # Création des nouvelles colonnes
    df["jours_depuis_derniere_maintenance"] = float("nan")
    df["nb_maintenances_precedentes"] = 0
    df["nb_maintenances_30j"] = 0
    df["nb_maintenances_correctives"] = 0

    # Parcours des équipements
    for id_equipement, groupe in df.groupby("id_equipement"):

        # Maintenances de cet équipement
        maintenances_equipement = df_maintenance[df_maintenance["id_equipement"] == id_equipement]

        # Parcours des observations
        for index, ligne in groupe.iterrows():

            date = ligne["date"]

            # Maintenances terminées avant l'observation
            maintenances_passees = maintenances_equipement[maintenances_equipement["date_fin"] <= date]

            # Nombre total de maintenances précédentes
            df.loc[index, "nb_maintenances_precedentes"] = len(maintenances_passees)

            # Maintenances des 30 derniers jours
            maintenances_30j = maintenances_passees[maintenances_passees["date_fin"] > date - pd.Timedelta(days=30)]

            df.loc[index, "nb_maintenances_30j"] = len(maintenances_30j)

            # Nombre de maintenances correctives
            df.loc[index, "nb_maintenances_correctives"] = (maintenances_passees["type_intervention"] == "corrective").sum()

            # Recherche de la dernière maintenance
            if not maintenances_passees.empty:

                derniere_maintenance = (maintenances_passees["date_fin"].max())

                df.loc[index, "jours_depuis_derniere_maintenance"] = ((date - derniere_maintenance).total_seconds()/ (24 * 3600))

    return df


#=====================================================
# 4.CREATION DES CIBLES 7j/ 14J/ 30J
#=====================================================
def creer_cibles_maintenance(df):

    # maintenance_dans_7j
    # maintenance_dans_14j
    # maintenance_dans_30j

    return df

#=====================================================
# 5.ANALYSES EXPLORATOIRES
#=====================================================

#=====================================================
# 6.MATRICE DE CORRELATION
#=====================================================

def afficher_matrice_correlation(df):

    colonnes_numeriques = df.select_dtypes(
        include=["number"]
    )

    correlation = colonnes_numeriques.corr()

    plt.figure(figsize=(12, 8))

    plt.imshow(
        correlation,
        aspect="auto"
    )

    plt.xticks(
        range(len(correlation.columns)),
        correlation.columns,
        rotation=90
    )

    plt.yticks(
        range(len(correlation.columns)),
        correlation.columns
    )

    plt.colorbar()

    plt.title(
        "Matrice de corrélation des variables"
    )

    plt.tight_layout()

    plt.show()

#==============================
# Bloc test
#==============================

    if __name__ == "__main__":
        df = charger_donnees_analytiques()

        df_ml = creer_features_temporelles(df)

        print(
            df_ml[
                [
                    "date_",
                    "annee",
                    "mois",
                    "jour",
                    "heure",
                    "minute_"
                ]
            ].head()
        )

if __name__ == "__main__":

    df = charger_donnees_analytiques()

    print(df.shape)
    print(df.head())
    print(df.dtypes)