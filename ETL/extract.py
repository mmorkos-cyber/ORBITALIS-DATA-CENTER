import os 
import pandas as pd
import sqlite3

root = os.path.dirname(os.path.abspath(__file__))
dossier_data = os.path.join(root, "orbitalis_data_large")

fichier_data_alarmes = os.path.join(dossier_data, "alarmes.json")
df_alarmes = pd.read_json(fichier_data_alarmes)


fichier_data_equipements = os.path.join(dossier_data, "equipements.csv")
df_equipement = pd.read_csv(fichier_data_equipements)

fichier_data_maintenance = os.path.join(dossier_data, "maintenance.csv")
df_maintenance = pd.read_csv(fichier_data_maintenance)

fichier_data_orbite = os.path.join(dossier_data, "orbite.csv")
df_orbite = pd.read_csv(fichier_data_orbite)

fichier_data_sites = os.path.join(dossier_data, "sites.csv")
df_sites = pd.read_csv(fichier_data_sites)

fichier_data_telemetrie = os.path.join(dossier_data, "telemetrie.csv")
df_telemetrie = pd.read_csv(fichier_data_telemetrie)

fichier_data_catalogues = os.path.join(dossier_data, "catalogue.db")
conn = sqlite3.connect(fichier_data_catalogues)
df_modeles = pd.read_sql_query("SELECT * FROM modeles;", conn)
df_seuils_alarmes = pd.read_sql_query("SELECT * FROM seuils_alarmes;", conn)
df_references_sites = pd.read_sql_query("SELECT * FROM references_sites;", conn)

conn.close()