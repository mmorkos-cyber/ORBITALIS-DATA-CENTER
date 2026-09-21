import os 
import pandas as pd
import sqlite3

root = os.path.dirname(os.path.abspath(__file__))
dossier_data = os.path.join(root, "orbitalis_data_large")

fichier_data_catalogues = os.path.join(dossier_data, "catalogue.db")
conn = sqlite3.connect(fichier_data_catalogues)

#print(pd.read_sql_query("PRAGMA table_info(modeles);", conn))
#print(pd.read_sql_query("PRAGMA table_info(seuils_alarmes);", conn))
#print(pd.read_sql_query("PRAGMA table_info(references_sites);", conn))
modeles = pd.read_sql_query("SELECT * FROM modeles;", conn)
seuils_alarmes = pd.read_sql_query("SELECT * FROM seuils_alarmes;", conn)
references_sites = pd.read_sql_query("SELECT * FROM references_sites;", conn)

print(references_sites.info())
print(references_sites.isna().sum())
print(references_sites.shape)
print(references_sites.duplicated().sum())
