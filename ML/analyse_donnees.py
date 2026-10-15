import pandas as pd
import matplotlib.pyplot as plt



#=====================================================
# 1. CHARGEMENT DES DONNEES
#=====================================================
def charger_donnees_analytiques():
    """
    Cette fonction sera complétée lorsque la BDD analytique
    sera disponible.
    """

    # À compléter plus tard :
    # connexion = sqlite3.connect(...)
    # df = pd.read_sql_query(...)

    pass

#=====================================================
# 2.PREPARATION DU DATAFRAME ML
#=====================================================

def preparer_dataframe_ml(df):

    df = df.copy()

    verifier_colonnes_ml(df)

    df["date_"] = pd.to_datetime(
        df["date_"],
        errors="coerce"
    )

    df["date_debut_maintenance"] = pd.to_datetime(
        df["date_debut_maintenance"],
        errors="coerce"
    )

    return df


def verifier_colonnes_ml(df):

    colonnes_attendues = [
        "id_equipement",
        "date_",
        "annee",
        "mois",
        "jour",
        "heure",
        "minute_",

        "type_equipement",
        "altitude_km",
        "duree_vie_restante",
        "masse_kg",

        "phase",
        "rayonnement_solaire_w_m2",
        "temperature_ambiante_c",

        "puissance_w",
        "puissance_nominale_w",
        "rayonnement",
        "courant_a",
        "tension_v",
        "temperature_c",
        "rendement_nominal",
        "performance",
        "perte_production",

        "id_maintenance",
        "type_intervention",
        "duree_maintenance",

        "id_alarme",
        "severite",
        "acquitte",
        "type_alarme",
        "seuil_warning",
        "seuil_critical",
        "unite"
    ]

    colonnes_manquantes = [
        colonne
        for colonne in colonnes_attendues
        if colonne not in df.columns
    ]

    if colonnes_manquantes:
        print("Colonnes manquantes :", colonnes_manquantes)
    else:
        print("Toutes les colonnes nécessaires sont présentes.")

#=====================================================
# 3.CREATION DES FEATURES
#=====================================================

features_candidates = [
    # Temps
    "annee",
    "mois",
    "jour",
    "heure",
    "minute",

    # Equipement
    "type_equipement",
    "altitude_km",
    "duree_vie_restante",
    "masse_kg",

    # Contexte orbital
    "phase",
    "rayonnement_solaire_w_m2",
    "temperature_ambiante_c",

    # Etat de production / télémétrie
    "puissance_w",
    "puissance_nominale_w",
    "rayonnement",
    "courant_a",
    "tension_v",
    "temperature_c",
    "rendement_nominal",
    "performance",
    "perte_production",

    # Alarmes
    "severite",
    "acquitte",
    "type_alarme",
    "seuil_warning",
    "seuil_critical"
]

features_garder = [
    "annee",
    "mois",
    "jour",
    "heure",
    "minute",

    "altitude_km",
    "duree_vie_restante",

    "rayonnement_solaire_w_m2",
    "temperature_ambiante_c",

    "puissance_w",
    "puissance_nominale_w",
    "rayonnement",
    "courant_a",
    "tension_v",
    "temperature_c",
    "rendement_nominal",

    "performance",
    "perte_production",

    "acquitte"
]

features_transformer = [
    "type_equipement",
    "phase",
    "severite",
    "type_alarme",
    "seuil_warning",
    "seuil_critical"
]

features_retirer = [
     "masse_kg"
]

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