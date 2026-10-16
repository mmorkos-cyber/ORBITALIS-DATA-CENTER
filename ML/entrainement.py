
# =====================================================
# 1. IMPORTS
# =====================================================
from pathlib import Path
import pandas as pd
from sklearn.metrics import classification_report
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    average_precision_score
)
import numpy as np


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
    print(X.columns.tolist())

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
# 8. ENTRAINEMENT REGRESSION LOGISTIQUE
# =====================================================

# Entraîne une régression logistique pour prédire
# une dégradation de l'équipement dans les 9 prochaines heures.

def entrainer_regression_logistique(X_train, y_train):

    # Préparer les variables pour la régression logistique
    preprocesseur = creer_preprocesseur(X_train, standardiser=True)

    # Créer le modèle
    modele = LogisticRegression(
        max_iter=500,
        solver="lbfgs",
        random_state=42
    )

    # Associer le prétraitement et le modèle
    pipeline = Pipeline([
        ("preprocesseur", preprocesseur),
        ("modele", modele)
    ])

    # Entraîner sur les données d'entraînement
    pipeline.fit(X_train, y_train)

    print("Régression logistique entraînée.")

    return pipeline

# =====================================================
# 9. ENTRAINEMENT DU RANDOM FOREST
# =====================================================

# Entraîne un Random Forest pour prédire une dégradation
# dans les 9 prochaines heures, avec des paramètres
# limitant le temps de calcul et la consommation mémoire.

def entrainer_random_forest(X_train, y_train):

    # Préparer les variables sans standardisation
    preprocesseur = creer_preprocesseur(X_train, standardiser=False)

    # Créer le modèle
    modele = RandomForestClassifier(
        n_estimators=50,
        max_depth=10,
        min_samples_leaf=5,
        n_jobs=2,
        random_state=42
    )

    # Associer le prétraitement et le modèle
    pipeline = Pipeline([
        ("preprocesseur", preprocesseur),
        ("modele", modele)
    ])

    # Entraîner le modèle
    pipeline.fit(X_train, y_train)

    print("Random Forest entraîné.")

    return pipeline


# =====================================================
# 10. EVALUATION DES MODELES
# =====================================================

# Évalue les prédictions d'un modèle avec les métriques
# de classification et les coûts métier d'Orbitalis.

def evaluer_modele(nom_modele, y_reel, predictions, probabilites=None):

    accuracy = accuracy_score(y_reel, predictions)
    precision = precision_score(y_reel, predictions, zero_division=0)
    recall = recall_score(y_reel, predictions, zero_division=0)
    f1 = f1_score(y_reel, predictions, zero_division=0)
    matrice = confusion_matrix(y_reel, predictions, labels=[0, 1])
    cout = calculer_cout_metier(y_reel, predictions)

    print(f"\nÉvaluation du modèle : {nom_modele}")
    print("Accuracy :", round(accuracy, 3))
    print("Précision :", round(precision, 3))
    print("Recall :", round(recall, 3))
    print("F1-score :", round(f1, 3))

    print("\nMatrice de confusion :")
    print(matrice)

    print("Coût métier :", cout, "€")

    if probabilites is not None:
        if len(set(y_reel)) == 2:
            pr_auc = average_precision_score(y_reel, probabilites)
            print("Average Precision (résumé de la courbe PR) :",
                  round(pr_auc, 3))

    return {
        "modele": nom_modele,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "cout_metier": cout
    }

# =====================================================
# 11. OPTIMISATION DU SEUIL DE DECISION
# =====================================================

# Recherche le seuil qui minimise le coût métier
# à partir des probabilités du jeu de validation.

def optimiser_seuil_metier(y_val, probabilites_val):

    meilleur_seuil = 0.50
    cout_minimum = float("inf")

    # Tester les seuils entre 0.05 et 0.95
    for seuil in np.arange(0.05, 0.96, 0.05):

        # Transformer les probabilités en prédictions 0 ou 1
        predictions = (probabilites_val >= seuil).astype(int)

        # Calculer le coût métier
        tn, fp, fn, tp = confusion_matrix(y_val, predictions, labels=[0, 1]).ravel()

        cout = (tp * 300 + fp * 150 + fn * 2500)

        # Conserver le seuil le moins coûteux
        if cout < cout_minimum:
            cout_minimum = cout
            meilleur_seuil = seuil

    print("Meilleur seuil :", round(meilleur_seuil, 2))
    print("Coût minimum sur la validation :", cout_minimum, "€")

    return meilleur_seuil

# =====================================================
# 12. COMPARAISON DES MODELES
# =====================================================

# Compare la baseline naïve, la régression logistique
# et le Random Forest sur le jeu de validation.

def comparer_modeles(df_val, X_val, y_val, modele_logistique, modele_forest):

    resultats = []

    # 1. Baseline naïve
    predictions_baseline = evaluer_baseline_naive(df_val)
    resultats_baseline = evaluer_modele("Baseline naïve", y_val, predictions_baseline)
    resultats.append(resultats_baseline)

    # 2. Régression logistique
    probabilites_logistique = (modele_logistique.predict_proba(X_val)[:, 1])
    seuil_logistique = optimiser_seuil_metier(y_val, probabilites_logistique)
    predictions_logistique = (probabilites_logistique >= seuil_logistique).astype(int)

    resultats_logistique = evaluer_modele(
        "Régression logistique",
        y_val,
        predictions_logistique,
        probabilites_logistique
    )

    resultats_logistique["seuil"] = seuil_logistique
    resultats.append(resultats_logistique)

    # 3. Random Forest
    probabilites_forest = (modele_forest.predict_proba(X_val)[:, 1])

    seuil_forest = optimiser_seuil_metier(y_val, probabilites_forest)

    predictions_forest = (probabilites_forest >= seuil_forest).astype(int)

    resultats_forest = evaluer_modele(
        "Random Forest",
        y_val,
        predictions_forest,
        probabilites_forest
    )

    resultats_forest["seuil"] = seuil_forest
    resultats.append(resultats_forest)

    # 4. Construire le tableau comparatif
    comparaison = pd.DataFrame(resultats)

    comparaison = comparaison.sort_values("cout_metier")

    print("\nComparaison des modèles :")
    print(comparaison.to_string(index=False))

    return comparaison

# =====================================================
# 13. EVALUATION FINALE SUR LE JEU DE TEST
# =====================================================

# Évalue le modèle retenu sur les données de test,
# avec le seuil sélectionné sur la validation.

def evaluer_modele_final(comparaison, modele_logistique, modele_forest, X_test, y_test, df_test):

    # Récupérer le modèle ayant le coût métier le plus faible
    meilleur = comparaison.iloc[0]

    nom_modele = meilleur["modele"]

    print("\nModèle retenu :", nom_modele)

    # Sélectionner le modèle et son seuil
    if nom_modele == "Régression logistique":
        modele = modele_logistique
        seuil = meilleur["seuil"]

    elif nom_modele == "Random Forest":
        modele = modele_forest
        seuil = meilleur["seuil"]

    else:
        # La baseline naïve ne nécessite pas de modèle ML
        predictions = evaluer_baseline_naive(df_test)

        resultats = evaluer_modele(
            "Baseline naïve - Test",
            y_test,
            predictions
        )

        return None, None, resultats

    # Calculer les probabilités sur le jeu de test
    probabilites = modele.predict_proba(X_test)[:, 1]

    # Appliquer le seuil déjà choisi sur la validation
    predictions = (probabilites >= seuil).astype(int)

    # Évaluer les prédictions
    resultats = evaluer_modele(
        nom_modele + " - Test",
        y_test,
        predictions,
        probabilites
    )

    print("Seuil utilisé :", round(seuil, 2))

    return modele, seuil, resultats

# =====================================================
# 14. SAUVEGARDE DU MODELE
# =====================================================
# À développer


# =====================================================
# 14. EXECUTION PRINCIPALE
# =====================================================
if __name__ == "__main__":
    pass