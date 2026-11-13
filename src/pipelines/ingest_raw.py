"""Entry point de compatibilidade para aquisição seletiva da Home Credit.

Use python -m src.pipelines.ingest_raw --plan para inspecionar o conjunto.
A implementação preserva arquivos existentes e não remove CSVs ou teste.
"""
from src.pipelines.download_home_credit import main


if __name__ == "__main__":
    main()
