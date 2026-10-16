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
# 1. CONFIGURATION
# =====================================================
BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "data" / "propre" / "base_analytique.db"

# =====================================================
# 2. CHARGEMENT ET VERIFICATION
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
            e.puissance_nominale_w, e.rendement_nominal,
            e.duree_vie_annees, e.masse_kg, e.altitude_km,
            o.phase, o.rayonnement_solaire_w_m2, o.temperature_ambiante_c,
            f.puissance_w, f.rayonnement, f.courant_a, f.tension_v,
            f.temperature_c, f.performance,
            f.perte_production_w, f.perte_energie_kwh
        FROM fait_production f
        JOIN dim_temps t ON f.id_temps = t.id_temps
        JOIN dim_equipement e ON f.id_equipement = e.id_equipement
        LEFT JOIN dim_orbite o ON f.id_orbite = o.id_orbite
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
            alarmes = pd.read_sql_query(
                """
                SELECT
                    a.alarme_id,
                    a.equipement_id AS id_equipement,
                    a.timestamp AS date_alarme,
                    a.severite,
                    a.acquittee,
                    s.type_alarme
                FROM alarmes a
                LEFT JOIN seuil_alarme s
                    ON a.id_seuil = s.id_seuil
                """,
                connexion
            )
            maintenance = pd.read_sql_query(
                "SELECT * FROM maintenance",
                  connexion)
            
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
        "puissance_nominale_w", "rendement_nominal", "duree_vie_annees",
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
        "puissance_nominale_w", "rendement_nominal", "duree_vie_annees",
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
# 3. CREATION DES FEATURES
# =====================================================

def creer_features_equipement(df):
    df = df.copy()
    installation = pd.to_datetime(df["date_installation"], utc=True, errors="coerce")
    df["age_equipement_annees"] = (df["date"] - installation).dt.total_seconds() / (365.25 * 86400)
    df["duree_vie_restante"] = (df["duree_vie_annees"] - df["age_equipement_annees"]).clip(lower=0)
    df["part_duree_vie_utilisee"] = df["age_equipement_annees"] / df["duree_vie_annees"].replace(0, np.nan)
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
        dates = groupe["date"].to_numpy(dtype="datetime64[ns]").astype("int64")
        dates_evt = evenements["date_alarme"].to_numpy(dtype="datetime64[ns]").astype("int64")
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
        dates = groupe["date"].to_numpy(dtype="datetime64[ns]").astype("int64")
        dates_evt = evenements["date_fin"].to_numpy(dtype="datetime64[ns]").astype("int64")
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
# 4. CREATION DE LA CIBLE A 9 HEURES
# =====================================================

def creer_seuil_degradation(df):

    df = df.copy().sort_values(
        ["id_equipement", "date"]
    )

    # =====================================================
    # 1. PERFORMANCE HORS ECLIPSE
    # =====================================================

    df["performance_hors_eclipse"] = df["performance"].where(
        df["phase"] == "ensoleillement"
    )

    # =====================================================
    # 2. REFERENCE HISTORIQUE GLISSANTE SUR 7 JOURS
    # =====================================================

    # Utiliser uniquement les mesures antérieures
    # à chaque observation

    df["performance_reference"] = (
        df.groupby("id_equipement", group_keys=False)
        .apply(
            lambda groupe: (
                groupe.set_index("date")["performance_hors_eclipse"]
                .rolling("7D", closed="left", min_periods=24)
                .mean()
                .set_axis(groupe.index)
            ),
            include_groups=False
        )
        .sort_index()
    )

    # =====================================================
    # 3. SEUIL GLISSANT : 80 % DE LA REFERENCE
    # =====================================================

    df["seuil_glissant"] = (
        df["performance_reference"] * 0.80
    )

    # =====================================================
    # 4. REFERENCE INITIALE PAR EQUIPEMENT
    # =====================================================

    # Prendre les premières 24 mesures valides hors éclipse.
    # La référence devient disponible après ces 24 mesures.
    # Elle reste ensuite figée pour chaque équipement.

    df["performance_initiale"] = np.nan

    for equipement, groupe in df.groupby("id_equipement"):

        performances = groupe[
            "performance_hors_eclipse"
        ].dropna()

        if len(performances) < 24:
            continue

        indices_initiaux = performances.index[:24]

        reference_initiale = performances.iloc[:24].mean()

        date_disponibilite = df.loc[
            indices_initiaux[-1], "date"
        ]

        masque = (
            (df["id_equipement"] == equipement)
            & (df["date"] > date_disponibilite)
        )

        df.loc[
            masque, "performance_initiale"
        ] = reference_initiale

    # =====================================================
    # 5. SEUIL PLANCHER : 60 % DE LA REFERENCE INITIALE
    # =====================================================

    df["seuil_plancher"] = (
        df["performance_initiale"] * 0.60
    )

    # =====================================================
    # 6. SEUIL FINAL DE DEGRADATION
    # =====================================================

    # On retient le plus élevé des deux seuils :
    # - seuil glissant
    # - seuil plancher
    #
    # Le plancher empêche le seuil de diminuer indéfiniment.

    df["seuil_degradation"] = df[
        ["seuil_glissant", "seuil_plancher"]
    ].max(axis=1, skipna=False)

    return df

def creer_cible_degradation(df, df_alarmes):

    df = df.copy().sort_values(
        ["id_equipement", "date"]
    ).reset_index(drop=True)

    alarmes = df_alarmes.copy()

    alarmes["date_alarme"] = pd.to_datetime(
        alarmes["date_alarme"],
        utc=True,
        errors="coerce"
    )

    alarmes = alarmes.dropna(
        subset=["id_equipement", "date_alarme"]
    )

    # =====================================================
    # 1. SELECTION DES ALARMES CRITIQUES
    # =====================================================

    alarmes = alarmes[
        (alarmes["severite"] == "critical")
        & alarmes["type_alarme"].isin([
            "perte_puissance",
            "surcharge",
            "surchauffe"
        ])
    ]

    alarmes_par_equipement = dict(
        tuple(
            alarmes.sort_values("date_alarme")
            .groupby("id_equipement")
        )
    )

    # =====================================================
    # 2. INITIALISATION DES VARIABLES
    # =====================================================

    # Ne conserver la performance que hors éclipse
    df["performance_hors_eclipse"] = df["performance"].where(
        df["phase"] == "ensoleillement"
    )

    df["performance_moyenne_future_9h"] = np.nan
    df["degradation_9h"] = np.nan

    duree = pd.Timedelta(hours=9).value

    # 108 mesures théoriques sur 9 heures, toutes phases confondues
    nb_mesures_min = 98

    # Minimum de mesures hors éclipse pour évaluer la performance
    nb_ensoleillees_min = 20

    # =====================================================
    # 3. CALCUL PAR EQUIPEMENT
    # =====================================================

    for equipement, groupe in df.groupby(
        "id_equipement",
        sort=False
    ):

        # Conversion explicite en nanosecondes
        dates = (
            groupe["date"]
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )

        performances = groupe[
            "performance_hors_eclipse"
        ].to_numpy(dtype=float)

        # Ce seuil intègre déjà :
        # - 80 % de la référence glissante sur 7 jours
        # - le plancher à 60 % de la référence initiale
        seuils = groupe[
            "seuil_degradation"
        ].to_numpy(dtype=float)

        # Fenêtre future : ]date actuelle ; date actuelle + 9 h]
        debut = np.searchsorted(
            dates,
            dates,
            side="right"
        )

        fin = np.searchsorted(
            dates,
            dates + duree,
            side="right"
        )

        # =====================================================
        # 4. PERFORMANCE MOYENNE FUTURE
        # =====================================================

        valides = np.isfinite(performances)

        sommes = np.concatenate((
            [0.0],
            np.cumsum(
                np.where(valides, performances, 0.0)
            )
        ))

        nombres = np.concatenate((
            [0],
            np.cumsum(valides)
        ))

        nb_valides = nombres[fin] - nombres[debut]

        moyennes = np.full(
            len(groupe),
            np.nan
        )

        np.divide(
            sommes[fin] - sommes[debut],
            nb_valides,
            out=moyennes,
            where=nb_valides > 0
        )

        # =====================================================
        # 5. VERIFICATION DE LA COUVERTURE TEMPORELLE
        # =====================================================

        # La période complète de 9 heures doit être disponible
        # avec au moins 98 mesures sur les 108 attendues.
        fenetre_couverte = (
            (dates + duree <= dates[-1])
            & ((fin - debut) >= nb_mesures_min)
        )

        # Pour évaluer la performance, il faut aussi
        # suffisamment de mesures ensoleillées.
        mesures_ensoleillees_suffisantes = (
            nb_valides >= nb_ensoleillees_min
        )

        # =====================================================
        # 6. ALARMES CRITIQUES DANS LES 9 HEURES FUTURES
        # =====================================================

        evenements = alarmes_par_equipement.get(equipement)

        if evenements is None or evenements.empty:

            presence_alarme = np.zeros(
                len(groupe),
                dtype=bool
            )

        else:

            dates_evt = (
                evenements["date_alarme"]
                .to_numpy(dtype="datetime64[ns]")
                .astype("int64")
            )

            debut_evt = np.searchsorted(
                dates_evt,
                dates,
                side="right"
            )

            fin_evt = np.searchsorted(
                dates_evt,
                dates + duree,
                side="right"
            )

            presence_alarme = (
                fin_evt > debut_evt
            )

        # =====================================================
        # 7. REGLES SELON LE TYPE D'EQUIPEMENT
        # =====================================================

        type_equipement = groupe[
            "type_equipement"
        ].iloc[0]

        if type_equipement in [
            "panneau_solaire",
            "convertisseur_DC"
        ]:

            # Une sous-performance est détectée lorsque
            # la moyenne future passe sous le seuil individuel.
            degradation_performance = (
                np.isfinite(moyennes)
                & np.isfinite(seuils)
                & mesures_ensoleillees_suffisantes
                & (moyennes < seuils)
            )

            # Si aucune alarme critique n'est présente,
            # il faut une moyenne future et un seuil fiables.
            cible_connue = (
                (
                    np.isfinite(moyennes)
                    & np.isfinite(seuils)
                    & mesures_ensoleillees_suffisantes
                )
                | presence_alarme
            )

        else:

            # Batteries et autres équipements :
            # uniquement les alarmes critiques.
            # Une batterie en recharge n'est donc pas
            # considérée comme dégradée à cause
            # de sa puissance négative.
            degradation_performance = np.zeros(
                len(groupe),
                dtype=bool
            )

            cible_connue = np.ones(
                len(groupe),
                dtype=bool
            )

        # =====================================================
        # 8. CREATION DE LA CIBLE BINAIRE
        # =====================================================

        cible = np.full(
            len(groupe),
            np.nan
        )

        # 1 = sous-performance ou alarme critique
        positif = (
            fenetre_couverte
            & (
                degradation_performance
                | presence_alarme
            )
        )

        # 0 = aucune dégradation identifiée
        negatif = (
            fenetre_couverte
            & cible_connue
            & ~degradation_performance
            & ~presence_alarme
        )

        cible[positif] = 1
        cible[negatif] = 0

        # =====================================================
        # 9. ENREGISTREMENT DES RESULTATS
        # =====================================================

        df.loc[
            groupe.index,
            "performance_moyenne_future_9h"
        ] = moyennes

        df.loc[
            groupe.index,
            "degradation_9h"
        ] = cible

    return df
# =====================================================
# 5. PIPELINE ET CONTROLES
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
    # Calculer un seuil propre à chaque équipement
    df = creer_seuil_degradation(df)
    # Construire la cible à 9 heures avec ce seuil
    df = creer_cible_degradation(df, df_alarmes)

    return df


def controler_resultat(df):

    print("\n" + "=" * 55)
    print("        BILAN DU DATASET ML ORBITALIS")
    print("=" * 55)

    # =====================================================
    # 1. INFORMATIONS GENERALES
    # =====================================================

    print("\n--- INFORMATIONS GENERALES ---")

    print(f"Nombre de lignes : {len(df):,}")
    print(f"Nombre de colonnes : {len(df.columns)}")
    print(f"Nombre d'équipements : {df['id_equipement'].nunique()}")
    print(f"Début : {df['date'].min()}")
    print(f"Fin   : {df['date'].max()}")

    # =====================================================
    # 2. REPARTITION DE LA CIBLE
    # =====================================================

    print("\n--- REPARTITION DE LA CIBLE ---")

    repartition = df["degradation_9h"].value_counts(
        dropna=False
    )

    print(repartition.to_string())

    nb_connues = df["degradation_9h"].notna().sum()
    nb_degradations = (df["degradation_9h"] == 1).sum()

    if nb_connues > 0:
        pourcentage = nb_degradations / nb_connues * 100
        print(f"\nDégradations parmi les cibles connues : {pourcentage:.2f} %")

    # =====================================================
    # 3. DEGRADATIONS PAR TYPE D'EQUIPEMENT
    # =====================================================

    print("\n--- DEGRADATIONS PAR TYPE D'EQUIPEMENT ---")

    bilan_types = (
        df.groupby("type_equipement")
        .agg(
            nb_mesures=("degradation_9h", "size"),
            normales=("degradation_9h", lambda x: (x == 0).sum()),
            degradations=("degradation_9h", lambda x: (x == 1).sum()),
            inconnues=("degradation_9h", lambda x: x.isna().sum())
        )
    )

    bilan_types["taux_degradation_pct"] = (
        bilan_types["degradations"]
        / (bilan_types["normales"] + bilan_types["degradations"])
        * 100
    ).round(2)

    print(bilan_types.to_string())

    # =====================================================
    # 4. RESUME DES SEUILS
    # =====================================================

    print("\n--- SEUILS DE DEGRADATION PAR TYPE ---")

    equipements = df[
        df["type_equipement"].isin([
            "panneau_solaire",
            "convertisseur_DC"
        ])
    ]

    resume_seuils = (
        equipements.groupby("type_equipement")
        .agg(
            reference_moyenne=("performance_reference", "mean"),
            seuil_glissant_moyen=("seuil_glissant", "mean"),
            seuil_plancher_moyen=("seuil_plancher", "mean"),
            seuil_final_moyen=("seuil_degradation", "mean")
        )
        .round(3)
    )

    print(resume_seuils.to_string())

    # =====================================================
    # 5. ACTIVATION DU SEUIL PLANCHER
    # =====================================================

    print("\n--- ACTIVATION DU SEUIL PLANCHER ---")

    plancher_actif = (
        equipements["seuil_plancher"]
        > equipements["seuil_glissant"]
    )

    print(f"Nombre de mesures avec plancher actif : {plancher_actif.sum():,}")

    if len(equipements) > 0:
        print(
            f"Pourcentage des mesures concernées : "
            f"{plancher_actif.mean() * 100:.2f} %"
        )

    # =====================================================
    # 6. VALEURS MANQUANTES IMPORTANTES
    # =====================================================

    print("\n--- VALEURS MANQUANTES ---")

    colonnes_a_verifier = [
        "phase",
        "performance",
        "performance_reference",
        "seuil_degradation",
        "degradation_9h"
    ]

    print(
        df[colonnes_a_verifier]
        .isna()
        .sum()
        .to_string()
    )

    # =====================================================
    # 7. CONCLUSION
    # =====================================================

    print("\n" + "=" * 55)
    print("FIN DU CONTROLE DU DATASET")
    print("=" * 55)


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


# =====================================================
# EXECUTION PRINCIPALE
# =====================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description="Préparation du dataset ML Orbitalis"
    )

    parser.add_argument(
        "--mode",
        choices=["test", "complet"],
        default="complet",
        help="Mode d'exécution : test ou complet"
    )

    args = parser.parse_args()

    # =====================================================
    # 1. CHEMINS
    # =====================================================

    BASE_DIR = Path(__file__).resolve().parent.parent

    chemin_analytique = (
        BASE_DIR / "data" / "propre" / "base_analytique.db"
    )

    chemin_historique = (
        BASE_DIR / "data" / "propre" / "orbital_data_center_clean.db"
    )

    dossier_sortie = (
        BASE_DIR / "data" / "propre" / "ml"
    )

    dossier_sortie.mkdir(
        parents=True,
        exist_ok=True
    )

    # =====================================================
    # 2. CHARGEMENT DES DONNEES
    # =====================================================

    df = charger_donnees_analytiques(chemin_analytique)

    df_alarmes, df_maintenance = charger_donnees_historiques(
        chemin_historique
    )

    print(
        f"Chargement : {len(df):,} mesures, "
        f"{len(df_alarmes)} alarmes, "
        f"{len(df_maintenance)} maintenances"
    )

    # =====================================================
    # 3. MODE TEST OU COMPLET
    # =====================================================

    if args.mode == "test":

        nombre_jours = 45

        equipements_test = (
            df["id_equipement"]
            .drop_duplicates()
            .head(3)
        )

        df = df[
            df["id_equipement"].isin(equipements_test)
        ].copy()

        premier_jour = pd.to_datetime(
            df["date"], utc=True
        ).min()

        df = df[
            pd.to_datetime(df["date"], utc=True)
            < premier_jour + pd.Timedelta(days=nombre_jours)
        ].copy()

        print(
            f"Mode test : {len(df):,} mesures "
            f"sur {df['id_equipement'].nunique()} équipements "
            f"/ {nombre_jours} jours"
        )

    # =====================================================
    # 4. PREPARATION DES DONNEES
    # =====================================================

    df = normaliser_mesures(df)

    print(
        f"Mesures à préparer : {len(df):,} "
        f"/ équipements : {df['id_equipement'].nunique()}"
    )

    df = creer_features_equipement(df)

    df = creer_features_telemetrie(df)

    df = creer_features_orbite(df)

    df = creer_features_alarmes(df, df_alarmes)

    df = creer_features_maintenance(df, df_maintenance)

    # =====================================================
    # 5. CREATION DU SEUIL ET DE LA CIBLE
    # =====================================================

    df = creer_seuil_degradation(df)

    df = creer_cible_degradation(df, df_alarmes)

    # =====================================================
    # 6. CONTROLE DU DATASET
    # =====================================================

    controler_resultat(df)

    # =====================================================
    # 7. ENREGISTREMENT DU DATASET
    # =====================================================

    if args.mode == "test":
        nom_fichier = "orbitalis_ml_test.parquet"
    else:
        nom_fichier = "orbitalis_ml_complet.parquet"

    chemin_sortie = dossier_sortie / nom_fichier

    df.to_parquet(
        chemin_sortie,
        index=False
    )

    print(f"\nDataset enregistré : {chemin_sortie}")


if __name__ == "__main__":
    main()