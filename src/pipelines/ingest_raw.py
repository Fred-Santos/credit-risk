from __future__ import annotations

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path


COMPETITION = "home-credit-credit-risk-model-stability"


def set_kaggle_config_env(repo_root: Path):
    # Se você mantém kaggle.json no repo root
    if os.environ.get("KAGGLE_CONFIG_DIR"):
        return
    local = repo_root / "kaggle.json"
    if local.exists():
        os.environ["KAGGLE_CONFIG_DIR"] = str(repo_root)


def raw_dir(repo_root: Path) -> Path:
    p = repo_root / "data" / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run(cmd):
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def unzip_all_and_delete_zips(dest_dir: Path):
    zips = sorted(dest_dir.rglob("*.zip"))
    print(f"Zips encontrados: {len(zips)}")
    for z in zips:
        print(f"Unzipping: {z}")
        try:
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(z.parent)
            z.unlink(missing_ok=True)  # apaga após extrair
        except zipfile.BadZipFile:
            print(f"WARNING: zip inválido (pulando): {z}")


def delete_csv_files_folder(dest_dir: Path):
    target = dest_dir / "csv_files"
    if target.exists() and target.is_dir():
        shutil.rmtree(target)
        print(f"Removido: {target}")
    else:
        print(f"csv_files não encontrado em: {dest_dir}")

def delete_test_parquet_folder(dest_dir: Path):
    target = dest_dir / "parquet_files" / "test"
    if target.exists() and target.is_dir():
        shutil.rmtree(target)
        print(f"Removido: {target}")
    else:
        print(f"test não encontrado em: {target}")


def main():
    repo_root = Path(__file__).resolve().parents[2]
    set_kaggle_config_env(repo_root)

    out_raw = raw_dir(repo_root)

    try:
        run(["kaggle", "competitions", "download", "-c", COMPETITION, "-p", str(out_raw)])
    except KeyboardInterrupt:
        print("Download cancelado pelo usuário.")
        return

    unzip_all_and_delete_zips(out_raw)
    delete_csv_files_folder(out_raw)
    delete_test_parquet_folder(out_raw)


    print(f"OK: ingestão raw concluída em {out_raw}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
