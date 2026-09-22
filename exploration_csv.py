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
