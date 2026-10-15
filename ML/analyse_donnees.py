"""Orbitalis - préparation du jeu de données de maintenance prédictive.

Exemples :
  python analyse_donnees.py --bdd-analytique data/orbital_data_center_analytics.db --bdd-clean data/orbital_data_center_clean.db
  python analyse_donnees.py --bdd-analytique data/orbital_data_center_analytics.db --bdd-clean data/orbital_data_center_clean.db --mode complet

Le mode test (par défaut) limite le volume à 3 équipements et 4 jours.
La cible à 9h doit être validée métier avant l'entraînement, notamment la
signification de la colonne performance pour chaque type d'équipement.
"""

import argparse
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


# =====================================================
# 1. CHARGEMENT ET VERIFICATION
# =====================================================

def charger_donnees_analytiques(chemin_bdd):
    chemin_bdd = Path(chemin_bdd)
    if not chemin_bdd.is_file():
        raise FileNotFoundError(f"Base analytique introuvable : {chemin_bdd}")

    requete = """
        SELECT
            f.id_production, f.id_equipement,
            t.date, t.annee, t.mois, t.jour, t.heure, t.minute,
            e.type_equipement, e.statut, e.date_installation,
            e.puissance_nominal_w, e.rendement_nomminal,
            e.duree_vie_annee, e.masse_kg, e.altitude_km,
            o.phase, o.rayonnement_solaire_w_m2, o.temperature_ambiante_c,
            f.puissance_w, f.rayonnement, f.courant_a, f.tension_v,
            f.temperature_c, f.performance,
            f.perte_production_w, f.perte_energie_kwh
        FROM FAIT_PRODUCTION f
        JOIN DIM_TEMPS t ON f.id_temps = t.id_temps
        JOIN DIM_EQUIPEMENT e ON f.id_equipement = e.id_equipement
        LEFT JOIN DIM_ORBITE o ON f.id_orbite = o.id_orbite
    """
    try:
        with sqlite3.connect(chemin_bdd) as connexion:
            return pd.read_sql_query(requete, connexion)
    except sqlite3.Error as erreur:
        raise RuntimeError(
            "Lecture analytique impossible : vérifier les noms des tables et "
            "colonnes (en particulier DIM_TEMPS.date/minute) avec le collègue. "
            f"Détail SQLite : {erreur}"
        ) from erreur


def charger_donnees_historiques(chemin_bdd):
    """Charge les événements depuis la base nettoyée, pas depuis les dimensions."""
    chemin_bdd = Path(chemin_bdd)
    if not chemin_bdd.is_file():
        raise FileNotFoundError(f"Base nettoyée introuvable : {chemin_bdd}")
    try:
        with sqlite3.connect(chemin_bdd) as connexion:
            alarmes = pd.read_sql_query("SELECT * FROM alarmes", connexion)
            maintenance = pd.read_sql_query("SELECT * FROM maintenance", connexion)
    except sqlite3.Error as erreur:
        raise RuntimeError(f"Lecture des historiques impossible : {erreur}") from erreur

    # Adapte les noms usuels de la base nettoyée à ceux utilisés par le ML.
    for tableau, type_evenement in [(alarmes, "alarmes"), (maintenance, "maintenance")]:
        if "id_equipement" not in tableau.columns and "equipement_id" in tableau.columns:
            tableau.rename(columns={"equipement_id": "id_equipement"}, inplace=True)
        attendues = (["id_equipement", "date_alarme", "severite", "type_alarme"]
                     if type_evenement == "alarmes"
                     else ["id_equipement", "date_fin", "type_intervention"])
        manquantes = [nom for nom in attendues if nom not in tableau.columns]
        if manquantes:
            raise ValueError(f"Colonnes manquantes dans {type_evenement} : {manquantes}. "
                             f"Disponibles : {tableau.columns.tolist()}")
    return alarmes, maintenance


def verifier_colonnes_ml(df):
    attendues = [
        "id_production", "id_equipement", "date", "annee", "mois", "jour",
        "heure", "minute", "type_equipement", "statut", "date_installation",
        "puissance_nominal_w", "rendement_nomminal", "duree_vie_annee",
        "masse_kg", "altitude_km", "phase", "rayonnement_solaire_w_m2",
        "temperature_ambiante_c", "puissance_w", "rayonnement", "courant_a",
        "tension_v", "temperature_c", "performance", "perte_production_w",
        "perte_energie_kwh",
    ]
    manquantes = [col for col in attendues if col not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes analytiques manquantes : {manquantes}")


def normaliser_mesures(df):
    df = df.copy()
    verifier_colonnes_ml(df)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["id_equipement", "date"])
    nombres = [
        "puissance_nominal_w", "rendement_nomminal", "duree_vie_annee",
        "masse_kg", "altitude_km", "rayonnement_solaire_w_m2",
        "temperature_ambiante_c", "puissance_w", "rayonnement", "courant_a",
        "tension_v", "temperature_c", "performance", "perte_production_w",
        "perte_energie_kwh",
    ]
    for col in nombres:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["id_equipement", "date"])
    nb_doublons = df.duplicated(["id_equipement", "date"]).sum()
    if nb_doublons:
        warnings.warn(
            f"{nb_doublons} mesures ont le même équipement et la même date. "
            "Une ligne par équipement/date est conservée (contrôler les jointures)."
        )
        df = df.drop_duplicates(["id_equipement", "date"], keep="first")
    return df.reset_index(drop=True)


# =====================================================
# 2. CREATION DES FEATURES
# =====================================================

def creer_features_equipement(df):
    df = df.copy()
    installation = pd.to_datetime(df["date_installation"], utc=True, errors="coerce")
    df["age_equipement_annees"] = (df["date"] - installation).dt.total_seconds() / (365.25 * 86400)
    df["duree_vie_restante"] = (df["duree_vie_annee"] - df["age_equipement_annees"]).clip(lower=0)
    df["part_duree_vie_utilisee"] = df["age_equipement_annees"] / df["duree_vie_annee"].replace(0, np.nan)
    return df


def creer_features_telemetrie(df):
    df = df.copy()
    variables = {
        "performance": ["mean", "std"],
        "puissance_w": ["mean", "std"],
        "temperature_c": ["mean", "max", "std"],
        "tension_v": ["mean", "std"],
        "courant_a": ["mean", "std"],
        "rayonnement": ["mean", "max"],
    }
    groupes = []
    for _, groupe in df.groupby("id_equipement", sort=False):
        groupe = groupe.copy().set_index("date")
        for colonne, statistiques in variables.items():
            for duree in ("1h", "6h", "24h"):
                historique = groupe[colonne].rolling(duree, min_periods=3)
                for statistique in statistiques:
                    groupe[f"{colonne}_{statistique}_{duree}"] = getattr(historique, statistique)()
        for colonne in ["performance", "puissance_w", "temperature_c", "tension_v", "courant_a"]:
            moyenne = groupe[colonne].rolling("1h", closed="left", min_periods=3).mean()
            groupe[f"{colonne}_ecart_moyenne_1h"] = groupe[colonne] - moyenne
        groupes.append(groupe.reset_index())
    return pd.concat(groupes, ignore_index=True) if groupes else df


def creer_features_orbite(df):
    df = df.copy()
    df["ecart_temperature"] = df["temperature_c"] - df["temperature_ambiante_c"]
    groupes = []
    for _, groupe in df.groupby("id_equipement", sort=False):
        groupe = groupe.copy().set_index("date")
        for colonne in ["rayonnement_solaire_w_m2", "temperature_ambiante_c", "ecart_temperature"]:
            for duree in ("1h", "6h", "24h"):
                historique = groupe[colonne].rolling(duree, min_periods=3)
                for statistique in ("mean", "max", "std"):
                    groupe[f"{colonne}_{statistique}_{duree}"] = getattr(historique, statistique)()
        for colonne in ["rayonnement_solaire_w_m2", "temperature_ambiante_c"]:
            moyenne = groupe[colonne].rolling("1h", closed="left", min_periods=3).mean()
            groupe[f"{colonne}_ecart_moyenne_1h"] = groupe[colonne] - moyenne
        groupes.append(groupe.reset_index())
    return pd.concat(groupes, ignore_index=True) if groupes else df


def creer_features_alarmes(df, df_alarmes):
    df = df.copy()
    alarmes = df_alarmes.copy()
    alarmes["date_alarme"] = pd.to_datetime(alarmes["date_alarme"], utc=True, errors="coerce")
    alarmes = alarmes.dropna(subset=["id_equipement", "date_alarme"])
    colonnes = ["nb_alarmes_1h", "nb_alarmes_6h", "nb_alarmes_24h", "nb_warning_24h",
                "nb_critical_24h", "nb_alarmes_puissance_24h", "nb_alarmes_temperature_24h"]
    for colonne in colonnes:
        df[colonne] = 0
    df["heures_depuis_derniere_alarme"] = np.nan
    alarmes_par_equipement = dict(tuple(alarmes.sort_values("date_alarme").groupby("id_equipement")))

    for equipement, groupe in df.groupby("id_equipement", sort=False):
        evenements = alarmes_par_equipement.get(equipement)
        if evenements is None or evenements.empty:
            continue
        dates = groupe["date"].astype("int64").to_numpy()
        dates_evt = evenements["date_alarme"].astype("int64").to_numpy()
        fin = np.searchsorted(dates_evt, dates, side="right")
        for heures in (1, 6, 24):
            debut = np.searchsorted(dates_evt, dates - pd.Timedelta(hours=heures).value, side="right")
            df.loc[groupe.index, f"nb_alarmes_{heures}h"] = fin - debut
        debut_24h = np.searchsorted(dates_evt, dates - pd.Timedelta(hours=24).value, side="right")
        categories = {
            "nb_warning_24h": evenements["severite"] == "warning",
            "nb_critical_24h": evenements["severite"] == "critical",
            "nb_alarmes_puissance_24h": evenements["type_alarme"].isin(["perte_puissance", "surcharge"]),
            "nb_alarmes_temperature_24h": evenements["type_alarme"] == "surchauffe",
        }
        for nom, condition in categories.items():
            cumul = np.concatenate(([0], np.cumsum(condition.to_numpy())))
            df.loc[groupe.index, nom] = cumul[fin] - cumul[debut_24h]
        deltas = np.full(len(groupe), np.nan)
        ok = fin > 0
        deltas[ok] = (dates[ok] - dates_evt[fin[ok] - 1]) / (3600 * 1e9)
        df.loc[groupe.index, "heures_depuis_derniere_alarme"] = deltas
    return df


def creer_features_maintenance(df, df_maintenance):
    df = df.copy()
    maintenance = df_maintenance.copy()
    maintenance["date_fin"] = pd.to_datetime(maintenance["date_fin"], utc=True, errors="coerce")
    maintenance = maintenance.dropna(subset=["id_equipement", "date_fin"])
    df["jours_depuis_derniere_maintenance"] = np.nan
    for nom in ("nb_maintenances_precedentes", "nb_maintenances_30j", "nb_maintenances_correctives"):
        df[nom] = 0
    maintenance_par_equipement = dict(tuple(maintenance.sort_values("date_fin").groupby("id_equipement")))
    for equipement, groupe in df.groupby("id_equipement", sort=False):
        evenements = maintenance_par_equipement.get(equipement)
        if evenements is None or evenements.empty:
            continue
        dates = groupe["date"].astype("int64").to_numpy()
        dates_evt = evenements["date_fin"].astype("int64").to_numpy()
        fin = np.searchsorted(dates_evt, dates, side="right")
        debut = np.searchsorted(dates_evt, dates - pd.Timedelta(days=30).value, side="right")
        df.loc[groupe.index, "nb_maintenances_precedentes"] = fin
        df.loc[groupe.index, "nb_maintenances_30j"] = fin - debut
        correctives = (evenements["type_intervention"] == "corrective").to_numpy()
        cumul = np.concatenate(([0], np.cumsum(correctives)))
        df.loc[groupe.index, "nb_maintenances_correctives"] = cumul[fin]
        deltas = np.full(len(groupe), np.nan)
        ok = fin > 0
        deltas[ok] = (dates[ok] - dates_evt[fin[ok] - 1]) / (86400 * 1e9)
        df.loc[groupe.index, "jours_depuis_derniere_maintenance"] = deltas
    return df


def creer_features_temporelles(df):
    df = df.copy()
    for colonne, valeur in {"annee": df["date"].dt.year, "mois": df["date"].dt.month,
                             "jour": df["date"].dt.day, "heure": df["date"].dt.hour,
                             "minute": df["date"].dt.minute}.items():
        df[colonne] = valeur
    return df


# =====================================================
# 3. CREATION DE LA CIBLE A 9 HEURES
# =====================================================

def creer_cible_degradation(df, df_alarmes):
    df = df.copy().sort_values(["id_equipement", "date"]).reset_index(drop=True)
    alarmes = df_alarmes.copy()
    alarmes["date_alarme"] = pd.to_datetime(alarmes["date_alarme"], utc=True, errors="coerce")
    alarmes = alarmes.dropna(subset=["id_equipement", "date_alarme"])
    alarmes = alarmes[
        (alarmes["severite"] == "critical") &
        alarmes["type_alarme"].isin(["perte_puissance", "surcharge", "surchauffe"])
    ]
    alarmes_par_equipement = dict(tuple(alarmes.sort_values("date_alarme").groupby("id_equipement")))

    df["performance_hors_eclipse"] = df["performance"].where(df["phase"] == "ensoleillement")
    df["performance_moyenne_future_9h"] = np.nan
    df["degradation_9h"] = np.nan
    duree = pd.Timedelta(hours=9).value
    # 9h / 5min = 108 mesures théoriques, tolérance de 10% d'absences.
    nb_mesures_min = 98

    for equipement, groupe in df.groupby("id_equipement", sort=False):
        dates = groupe["date"].astype("int64").to_numpy()
        performances = groupe["performance_hors_eclipse"].to_numpy(dtype=float)
        debut = np.searchsorted(dates, dates, side="right")
        fin = np.searchsorted(dates, dates + duree, side="right")
        valides = np.isfinite(performances)
        sommes = np.concatenate(([0.0], np.cumsum(np.where(valides, performances, 0.0))))
        nombres = np.concatenate(([0], np.cumsum(valides)))
        nb_valides = nombres[fin] - nombres[debut]
        moyennes = np.full(len(groupe), np.nan)
        np.divide(sommes[fin] - sommes[debut], nb_valides, out=moyennes, where=nb_valides > 0)

        # Dernière mesure disponible + au moins 90 % des horodatages attendus.
        fenetre_couverte = (dates + duree <= dates[-1]) & ((fin - debut) >= nb_mesures_min)
        evenements = alarmes_par_equipement.get(equipement)
        if evenements is None or evenements.empty:
            presence_alarme = np.zeros(len(groupe), dtype=bool)
        else:
            dates_evt = evenements["date_alarme"].astype("int64").to_numpy()
            debut_evt = np.searchsorted(dates_evt, dates, side="right")
            fin_evt = np.searchsorted(dates_evt, dates + duree, side="right")
            presence_alarme = fin_evt > debut_evt

        cible = np.full(len(groupe), np.nan)
        # Conserver une cible inconnue si la fenêtre n'est pas assez observée.
        positif = fenetre_couverte & ((moyennes < 0.65) | presence_alarme)
        negatif = fenetre_couverte & np.isfinite(moyennes) & (moyennes >= 0.65) & ~presence_alarme
        cible[positif] = 1
        cible[negatif] = 0
        df.loc[groupe.index, "performance_moyenne_future_9h"] = moyennes
        df.loc[groupe.index, "degradation_9h"] = cible
    return df


# =====================================================
# 4. PIPELINE ET CONTROLES
# =====================================================

def preparer_dataframe_ml(df, df_alarmes, df_maintenance):
    df = normaliser_mesures(df)
    if df.empty:
        raise ValueError("Aucune mesure exploitable après nettoyage des dates.")
    print(f"Mesures à préparer : {len(df):,} / équipements : {df['id_equipement'].nunique()}")
    df = creer_features_equipement(df)
    df = creer_features_telemetrie(df)
    df = creer_features_orbite(df)
    df = creer_features_alarmes(df, df_alarmes)
    df = creer_features_maintenance(df, df_maintenance)
    df = creer_cible_degradation(df, df_alarmes)
    return df


def controler_resultat(df):
    print("\n=== CONTROLE DU DATASET ===")
    print("Dimensions :", df.shape)
    print("Période :", df["date"].min(), "→", df["date"].max())
    print("Équipements :", df["id_equipement"].nunique())
    print("Répartition de la cible (y compris NaN) :")
    print(df["degradation_9h"].value_counts(dropna=False).to_string())
    print("Exemple :")
    print(df[["id_equipement", "date", "performance_moyenne_future_9h", "degradation_9h"]].head(8).to_string(index=False))
    print("\nATTENTION : cible exploratoire, valider la définition métier de performance.")
    print("ATTENTION : contrôler les imputations ETL (bfill/interpolation utilisant le futur).")
    print("Ne jamais inclure performance_moyenne_future_9h ou performance_hors_eclipse comme features futures.")


def afficher_matrice_correlation(df, chemin_sortie, nombre_max=25):
    """Option facultative, limitée pour préserver la mémoire et la lisibilité."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    exclues = {"degradation_9h", "performance_moyenne_future_9h", "performance_hors_eclipse",
                "id_production", "annee", "mois", "jour", "minute"}
    colonnes = [c for c in df.select_dtypes(include="number").columns if c not in exclues]
    colonnes = colonnes[:nombre_max]
    if not colonnes:
        return
    correlation = df[colonnes].corr()
    fig, ax = plt.subplots(figsize=(11, 9))
    image = ax.imshow(correlation, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(colonnes)), labels=colonnes, rotation=90, fontsize=7)
    ax.set_yticks(range(len(colonnes)), labels=colonnes, fontsize=7)
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(chemin_sortie, dpi=120)
    plt.close(fig)


def main():
    racine = Path(__file__).resolve().parent
    analyseur = argparse.ArgumentParser(description="Préparation des données ML Orbitalis")
    analyseur.add_argument("--bdd-analytique", type=Path,
                           default=racine / "data" / "orbital_data_center_analytics.db")
    analyseur.add_argument("--bdd-clean", type=Path,
                           default=racine / "data" / "orbital_data_center_clean.db")
    analyseur.add_argument("--mode", choices=["test", "complet"], default="test")
    analyseur.add_argument("--sortie", type=Path, default=racine / "data" / "ml")
    analyseur.add_argument("--correlation", action="store_true")
    args = analyseur.parse_args()

    df = charger_donnees_analytiques(args.bdd_analytique)
    alarmes, maintenance = charger_donnees_historiques(args.bdd_clean)
    print(f"Chargement : {len(df):,} mesures, {len(alarmes):,} alarmes, {len(maintenance):,} maintenances")

    if args.mode == "test":
        # Garder un bloc chronologique de 4 jours et 3 équipements.
        # Les fenêtres de 24h et la cible de 9h disposent alors d'historique.
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        premier_jour = df["date"].min()
        ids = df["id_equipement"].dropna().drop_duplicates().head(3)
        df = df[
            df["id_equipement"].isin(ids)
            & (df["date"] < premier_jour + pd.Timedelta(days=4))
        ].copy()
        print(f"Mode test : {len(df):,} mesures sur 3 équipements maximum / 4 jours")

    resultat = preparer_dataframe_ml(df, alarmes, maintenance)
    controler_resultat(resultat)

    args.sortie.mkdir(parents=True, exist_ok=True)
    nom = "orbitalis_ml_test" if args.mode == "test" else "orbitalis_ml_complet"
    chemin = args.sortie / f"{nom}.parquet"
    try:
        resultat.to_parquet(chemin, index=False)
    except (ImportError, ModuleNotFoundError):
        chemin = args.sortie / f"{nom}.csv"
        resultat.to_csv(chemin, index=False)
        print("Parquet indisponible (installer pyarrow pour un fichier plus compact).")
    print("Dataset enregistré :", chemin)

    if args.correlation:
        image = args.sortie / f"{nom}_correlation.png"
        afficher_matrice_correlation(resultat, image)
        print("Matrice de corrélation :", image)


if __name__ == "__main__":
    main()
