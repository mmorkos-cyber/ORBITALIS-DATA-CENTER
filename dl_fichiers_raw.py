import requests
import zipfile
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
ARCHIVE_DIR = BASE_DIR / "data" / "archive"
ARCHIVE_FILE = ARCHIVE_DIR / "orbitalis-datasets-large.zip"

URL = "https://simplonline-v3-prod.s3.eu-west-3.amazonaws.com/media/file/zip/orbitalis-datasets-large-6ab117db9433f326494741.zip"


def download_data():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    

    print(f"Téléchargement de {ARCHIVE_FILE.name}...")
    with requests.get(URL, stream=True, timeout=60) as response:
        if response.status_code != 200:
            print(f"Impossible de télécharger (HTTP {response.status_code})")
            return None

        with open(ARCHIVE_FILE, "wb") as f:
            for morceau in response.iter_content(chunk_size=1024 * 1024):
                f.write(morceau)

    print("Téléchargement terminé !")
    return ARCHIVE_FILE


def extract_archive():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ARCHIVE_FILE, "r") as zf:
        for membre in zf.infolist():
            if membre.is_dir():
                continue

            nom_fichier = Path(membre.filename).name
            with zf.open(membre) as source, open(RAW_DIR / nom_fichier, "wb") as cible:
                shutil.copyfileobj(source, cible)

    print(f"Archive extraite dans {RAW_DIR}")

def raw_contient_fichiers():
    return RAW_DIR.exists() and any(RAW_DIR.iterdir())


def run():
    if raw_contient_fichiers():
        print(f"{RAW_DIR} contient déjà des fichiers, extraction ignorée.")
        return

    if ARCHIVE_FILE.exists() or download_data():
        extract_archive()