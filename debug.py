import os
import pandas as pd
import sqlite3

dossier = os.path.join("data", "traite")

# --- Équipements bruts ---
eq = pd.read_csv(os.path.join(dossier, "equipements.csv"))
print("=== equipements.csv ===")
print("Colonnes :", list(eq.columns))
print("Nombre de lignes :", len(eq))
print("Doublons exacts :", eq.duplicated().sum())
print("Valeurs manquantes par colonne :")
print(eq.isna().sum())
print(eq.head(10))

# --- Modèles du catalogue ---
conn = sqlite3.connect(os.path.join(dossier, "catalogue.db"))
mod = pd.read_sql_query("SELECT * FROM modeles;", conn)
conn.close()
print("\n=== catalogue.db / modeles ===")
print(mod[["modele_id", "type_equipement"]])

# --- Correspondance modèles ---
print("\n=== Valeurs de 'modele' dans equipements.csv ===")
print(eq["modele"].unique())