from dl_fichiers_raw import run
from pipeline_base_analytique import load_base_analytique

def main():
    
    print("=== Étape 1 : téléchargement et extraction ===")
    run()

    print("=== Étape 2 : construction de la base relationnelle ===")
    from ETL import load
    load.run()

    print("=== Étape 3 : construction de la base analytique ===")
    load_base_analytique.run()


if __name__ == "__main__":
    main()