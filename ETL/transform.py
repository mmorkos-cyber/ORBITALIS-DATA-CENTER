import numpy as np
from extract import df_alarmes, df_equipement, df_maintenance, df_orbite, df_sites, df_telemetrie, df_modeles, df_seuils_alarmes, df_references_sites
import pandas as pd

#Normaliser les timestamp et les les dates

patterns = {
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$': '%Y-%m-%dT%H:%M:%S',
    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}Z$': '%Y-%m-%d %H:%M:%S.%fZ',
    r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$': '%d/%m/%Y %H:%M',
    r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$': '%Y/%m/%d %H:%M',
}

timestamp_brut = df_telemetrie['timestamp'].astype(str)

df_telemetrie['timestamp'] = pd.Series(pd.NaT, index=df_telemetrie.index, dtype='datetime64[ns]')

for pat, fmt in patterns.items():
    mask = timestamp_brut.str.match(pat)
    df_telemetrie.loc[mask, 'timestamp'] = pd.to_datetime(timestamp_brut[mask], format=fmt)

df_orbite['timestamp'] = pd.to_datetime(df_orbite['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce').astype('datetime64[ns]')
df_alarmes['timestamp'] = pd.to_datetime(df_alarmes['timestamp'], format='%Y-%m-%d %H:%M:%S', errors='coerce').astype('datetime64[ns]')

df_maintenance['date_debut'] = pd.to_datetime(df_maintenance['date_debut'], format='%Y-%m-%d', errors='coerce').astype('datetime64[ns]')
df_maintenance['date_fin'] = pd.to_datetime(df_maintenance['date_fin'], format='%Y-%m-%d', errors='coerce').astype('datetime64[ns]')

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

df_sites.loc[df_sites['site_id'] == 'SITE-003', 'altitude_km'] = (df_references_sites.loc[df_references_sites['site_id'] == 'SITE-003', 'zone_orbitale'].str.extract(r'(\d+)km')[0].astype(float).values[0])
df_sites.loc[df_sites['site_id'] == 'SITE-004', 'inclination_deg'] = 97.6


df_modeles.loc[(df_modeles['type_equipement'] == 'radiateur') & (df_modeles['rendement_nominal'].isna()), 'rendement_nominal'] = 0.0

df_seuils_alarmes.loc[df_seuils_alarmes['type_alarme'] == 'capteur_defaillant', ['seuil_warning', 'seuil_critical', 'unite']] = [0.0, 0.0, 'N/A']

df_references_sites.loc[df_references_sites['site_id'] == 'SITE-003', 'description'] = 'Module Gamma'

df_references_sites.loc[df_references_sites['site_id'] == 'SITE-004', 'capacite_max_kw'] = (df_references_sites['capacite_max_kw'].mean())

df_telemetrie['puissance_w'] = df_telemetrie['puissance_w'].replace([1000000.0, 99999.0], np.nan)
df_telemetrie['temperature_c'] = df_telemetrie['temperature_c'].replace([999.0, 450.0, 280.0, -250.0, -180.0], np.nan)


df_telemetrie = df_telemetrie.merge(df_equipement[['equipement_id', 'site_id', 'type']], on='equipement_id', how='left')
mask_anomalie = (df_telemetrie['puissance_w'] < 0) & (df_telemetrie['type'].isin(['panneau_solaire', 'convertisseur_DC']))
df_telemetrie.loc[mask_anomalie, 'puissance_w'] = np.nan


df_telemetrie['timestamp_arrondi'] = df_telemetrie['timestamp'].dt.round('15min')

# Jointure classique, comme pour equipement
df_telemetrie = df_telemetrie.merge(
    df_orbite[['timestamp', 'site_id', 'phase']],
    left_on=['site_id', 'timestamp_arrondi'],
    right_on=['site_id', 'timestamp'],
    how='left',
    suffixes=('', '_orbite')
)

df_telemetrie = df_telemetrie.drop(columns=['timestamp_arrondi', 'timestamp_orbite'])

mask_eclipse = df_telemetrie['puissance_w'].isna() & (df_telemetrie['phase'] == 'eclipse')
df_telemetrie.loc[mask_eclipse, 'puissance_w'] = 0.0

df_telemetrie = df_telemetrie.sort_values(['equipement_id', 'timestamp'])
df_telemetrie['temperature_c'] = (df_telemetrie.groupby('equipement_id')['temperature_c'].transform(lambda x: x.interpolate(method='linear')))
df_telemetrie['temperature_c'] = (df_telemetrie.groupby('equipement_id')['temperature_c'].transform(lambda x: x.ffill().bfill()))


mask_p = df_telemetrie['puissance_w'].isna() & df_telemetrie['tension_v'].notna() & df_telemetrie['courant_a'].notna()
df_telemetrie.loc[mask_p, 'puissance_w'] = df_telemetrie.loc[mask_p, 'tension_v'] * df_telemetrie.loc[mask_p, 'courant_a']

mask_t = df_telemetrie['tension_v'].isna() & df_telemetrie['puissance_w'].notna() & df_telemetrie['courant_a'].notna()
df_telemetrie.loc[mask_t, 'tension_v'] = df_telemetrie.loc[mask_t, 'puissance_w'] / df_telemetrie.loc[mask_t, 'courant_a']

mask_c = df_telemetrie['courant_a'].isna() & df_telemetrie['puissance_w'].notna() & df_telemetrie['tension_v'].notna()
df_telemetrie.loc[mask_c, 'courant_a'] = df_telemetrie.loc[mask_c, 'puissance_w'] / df_telemetrie.loc[mask_c, 'tension_v']

cols = ['puissance_w', 'tension_v', 'courant_a']
df_telemetrie[cols] = df_telemetrie.groupby('equipement_id')[cols].transform(lambda x: x.interpolate(method='linear'))
df_telemetrie[cols] = df_telemetrie.groupby('equipement_id')[cols].transform(lambda x: x.ffill().bfill())

df_telemetrie = df_telemetrie.drop(columns=['site_id', 'phase'])