from pathlib import Path
import joblib
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent

MODELE_FICHIER = BASE_DIR / "data" / "propre" / "ml" / "modeles" / "modele_degradation.joblib"

DATASET_FICHIER = BASE_DIR / "data" / "propre" / "ml" / "orbitalis_ml_complet.parquet"

#=====================================================
# 1. CHARGEMENT DU MODELE ENTRAÎNE
#=====================================================
modele = joblib.load(MODELE_FICHIER)

pipeline = modele["pipeline"]
seuil = modele["seuil_decision"]

#=====================================================
# 2. PREPARATION D'UNE NOUVELLE OBSERVATION
#=====================================================
df = pd.read_parquet(DATASET_FICHIER)
df["date"] = pd.to_datetime(df["date"], utc=True)

dernieres = (
    df.sort_values("date")
      .groupby("id_equipement")
      .tail(1)
)

X_nouveau = dernieres.reindex(columns=pipeline.feature_names_in_)

X_nouveau = X_nouveau.replace([np.inf, -np.inf], np.nan)

#=====================================================
# 3. PREDICTION DU RISQUE DE MAINTENANCE
#=====================================================

probabilites = pipeline.predict_proba(X_nouveau)[:, 1]
alertes = (probabilites >= seuil).astype(int)

resultats = pd.DataFrame({
    "id_equipement": dernieres["id_equipement"].values,
    "type_equipement": dernieres["type_equipement"].values,
    "date": dernieres["date"].values,
    "probabilite_degradation": probabilites.round(3),
    "alerte_maintenance": alertes
}).sort_values("probabilite_degradation", ascending=False)

print(f"Seuil de décision : {seuil:.2f}")
print(resultats.to_string(index=False))