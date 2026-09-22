from extract import df_alarmes, df_equipement, df_maintenance, df_orbite, df_sites, df_telemetrie, df_modeles, df_seuils_alarmes, df_references_sites
import pandas as pd

#Normaliser les timestamp et les les dates

pd.to_datetime(df_orbite['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
pd.to_datetime(df_telemetrie['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
pd.to_datetime(df_alarmes['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

pd.to_datetime(df_maintenance['date_debut'], format='%Y-%m-%d', errors='coerce')
pd.to_datetime(df_maintenance['date_fin'], format='%Y-%m-%d', errors='coerce')

#Supression des doublons

df_equipement.drop_duplicates(keep='first', inplace=True)
df_telemetrie.drop_duplicates(keep='first', inplace=True)

#Traitement des valeurs manquantes/aberrantes

df_alarmes['equipement_id'] = df_alarmes['equipement_id'].fillna(df_alarmes['message'].str.extract(r'(EQ-\d+)')[0])

df_equipement.dropna(subset=['site_id', 'modele'], inplace=True)

df_maintenance.dropna(subset=['equipement_id'], inplace=True)
df_maintenance.loc[df_maintenance['commentaire'].isna(), 'commentaire'] = 'RAS'
df_maintenance.loc[df_maintenance['technicien'].isna(), 'technicien'] = 'technicien non renseigné'


df_orbite = df_orbite.sort_values(['site_id', 'timestamp'])
df_orbite['temperature_ambiante_c'] = (df_orbite.groupby('site_id')['temperature_ambiante_c'].transform(lambda x: x.interpolate(method='linear')))
print(df_orbite[df_orbite.isna().any(axis=1)])

#df.loc[df['col'].isna(), 'col'] = 'valeur_corrigee'