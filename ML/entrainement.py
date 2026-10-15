
# =====================================================
# 1. IMPORTS
# =====================================================
from pathlib import Path
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# =====================================================
# 2. CHARGEMENT DU DATASET ML
# =====================================================

def charger_dataset_ml(chemin_fichier):

    chemin_fichier = Path(chemin_fichier)

    if not chemin_fichier.is_file():
        raise FileNotFoundError(f"Dataset ML introuvable : {chemin_fichier}")

    if chemin_fichier.suffix == ".parquet":
        df = pd.read_parquet(chemin_fichier)

    elif chemin_fichier.suffix == ".csv":
        df = pd.read_csv(chemin_fichier)

    else:
        raise ValueError("Format non pris en charge. Utiliser CSV ou Parquet.")

    print("Dataset chargé :", df.shape)

    return df

# =====================================================
# 3. PREPARATION DES FEATURES X ET DE LA CIBLE Y
# =====================================================
def preparer_X_y(df):

    df = df.copy()

    # Retirer les observations sans cible
    df = df.dropna(subset=["degradation_9h"])

    # Définir les colonnes à exclure des features
    colonnes_exclues = [
        "id_production",
        "id_equipement",
        "date",
        "date_installation",
        "degradation_9h",
        "performance_moyenne_future_9h",
        "performance_hors_eclipse",
        "statut",
        "annee",
        "mois",
        "jour",
        "minute"
    ]

    # Sélectionner les features
    X = df.drop(
        columns=colonnes_exclues,
        errors="ignore"
    )

    # Sélectionner la cible
    y = df["degradation_9h"].astype(int)

    print("Nombre d'observations :", len(df))
    print("Nombre de features :", X.shape[1])

    return X, y, df

# =====================================================
# 4. DECOUPAGE CHRONOLOGIQUE
# =====================================================

def decouper_donnees_temporelles(X, y, df):

    # Copier les dates pour travailler chronologiquement
    dates = pd.to_datetime(df["date"], utc=True)

    # Récupérer les dates distinctes dans l'ordre
    dates_uniques = dates.drop_duplicates().sort_values()

    # Définir les limites des trois périodes
    limite_train = dates_uniques.iloc[int(len(dates_uniques) * 0.70)]
    limite_validation = dates_uniques.iloc[int(len(dates_uniques) * 0.85)]

    # Marge de sécurité de 9 heures
    marge = pd.Timedelta(hours=9)

    # Définir les observations de chaque période
    masque_train = dates < limite_train - marge

    masque_validation = (
        (dates >= limite_train) &
        (dates < limite_validation - marge)
    )

    masque_test = dates >= limite_validation

    # Séparer les features et les cibles
    X_train = X.loc[masque_train]
    X_val = X.loc[masque_validation]
    X_test = X.loc[masque_test]

    y_train = y.loc[masque_train]
    y_val = y.loc[masque_validation]
    y_test = y.loc[masque_test]

    # Afficher les tailles des ensembles
    print("Train :", len(X_train), "observations")
    print("Validation :", len(X_val), "observations")
    print("Test :", len(X_test), "observations")

    return X_train, X_val, X_test, y_train, y_val, y_test

# =====================================================
# 5. BASELINE NAIVE
# =====================================================

def evaluer_baseline_naive(df):

    # Ne conserver que les observations avec une cible connue
    df = df.dropna(subset=["degradation_9h"]).copy()

    # Cible réelle
    y_reel = df["degradation_9h"].astype(int)

    # Prédiction naïve à partir de la performance actuelle
    prediction = (
        (df["phase"] == "ensoleillement") &
        (df["performance"] < 0.65)
    ).astype(int)

    # Afficher les résultats
    print("Matrice de confusion :")
    print(confusion_matrix(y_reel, prediction, labels=[0, 1]))

    print("\nRapport de classification :")
    print(classification_report(
        y_reel,
        prediction,
        labels=[0, 1],
        zero_division=0
    ))

    return prediction

# =====================================================
# 6. CALCUL DU COUT METIER
# =====================================================
def calculer_cout_metier(y_reel, prediction):

    # Récupérer les résultats de la matrice de confusion
    tn, fp, fn, tp = confusion_matrix(
        y_reel,
        prediction,
        labels=[0, 1]
    ).ravel()

    # Calculer le coût de chaque situation
    cout_total = (
        tp * 300 +
        fp * 150 +
        fn * 2500
    )

    print("Vrais positifs :", tp)
    print("Faux positifs :", fp)
    print("Faux négatifs :", fn)
    print("Vrais négatifs :", tn)

    print("Coût métier total :", cout_total, "€")

    return cout_total

# =====================================================
# 7. PRETRAITEMENT DES DONNEES
# =====================================================

# Prépare les variables pour l'entraînement des modèles :
# - Remplace les valeurs numériques manquantes par la médiane.
# - Transforme les variables catégorielles en variables numériques.
# - Standardise les variables numériques si nécessaire.
# Les transformations seront apprises uniquement sur le jeu d'entraînement afin d'éviter les fuites de données.

def creer_preprocesseur(X, standardiser=True):

    # Identifier les colonnes numériques
    colonnes_numeriques = X.select_dtypes(include=["number"]).columns.tolist()

    # Identifier les colonnes catégorielles
    colonnes_categorielles = X.select_dtypes(include=["object", "category", "string"]).columns.tolist()

    # Préparation des variables numériques
    pipeline_numerique = Pipeline([
        ("imputation", SimpleImputer(strategy="median")),
        ("standardisation", StandardScaler())
    ] if standardiser else [
        ("imputation", SimpleImputer(strategy="median"))
    ])

    # Préparation des variables catégorielles
    pipeline_categoriel = Pipeline([
        ("imputation", SimpleImputer(
            strategy="constant",
            fill_value="inconnu"
        )),
        ("encodage", OneHotEncoder(handle_unknown="ignore"))
    ])

    # Regrouper les transformations
    preprocesseur = ColumnTransformer([
        ("numerique", pipeline_numerique, colonnes_numeriques),
        ("categoriel", pipeline_categoriel, colonnes_categorielles)
    ])

    return preprocesseur

# =====================================================
# 8. ENTRAINEMENT DES MODELES
# =====================================================
# À développer


# =====================================================
# 9. EVALUATION ET COMPARAISON DES MODELES
# =====================================================
# À développer


# =====================================================
# 10. SAUVEGARDE DU MODELE
# =====================================================
# À développer


# =====================================================
# 11. EXECUTION PRINCIPALE
# =====================================================
if __name__ == "__main__":
    pass