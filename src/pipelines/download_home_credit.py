"""Aquisição seletiva da Home Credit via cliente oficial Kaggle.

Publicação por arquivo com journal e checksum. Nenhum dado antigo é removido.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile
from src.utils.paths import load_paths

COMPETITION = "home-credit-credit-risk-model-stability"
FILES = (
    "feature_definitions.csv",
    "parquet_files/train/train_base.parquet",
    "parquet_files/train/train_static_0_0.parquet",
    "parquet_files/train/train_static_0_1.parquet",
    "parquet_files/train/train_applprev_1_0.parquet",
    "parquet_files/train/train_applprev_1_1.parquet",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_record(path: Path, record: dict):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _fetch(remote: str, stage: Path):
    command = [sys.executable, "-m", "kaggle", "competitions", "download",
               COMPETITION, "--file", remote, "--path", str(stage), "--quiet"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Tempo limite no download de {remote}; tente novamente") from exc
    if result.returncode:
        # Não inclui respostas/signed URLs do cliente nos relatórios do projeto.
        raise RuntimeError(
            f"Kaggle não concluiu {remote}. Verifique autenticação, acesso à competição "
            "e rede. Configure: bash scripts/project.sh -m kaggle auth login --no-launch-browser")


def _payload(stage: Path, remote: str) -> Path:
    for candidate in (stage / remote, stage / PurePosixPath(remote).name):
        if candidate.is_file():
            return candidate
    archives = list(stage.rglob("*.zip"))
    if len(archives) != 1:
        raise RuntimeError(f"Arquivo esperado não encontrado no download: {remote}")
    with zipfile.ZipFile(archives[0]) as bundle:
        members = [info for info in bundle.infolist() if not info.is_dir()]
        if len(members) != 1 or members[0].filename not in {remote, PurePosixPath(remote).name}:
            raise RuntimeError(f"Conteúdo ZIP diferente do arquivo solicitado: {remote}")
        output = stage / "payload"
        with bundle.open(members[0]) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)
        return output


def download_selected(raw: Path, files=FILES, *, fetch=_fetch) -> list[dict]:
    # MVP validado em Linux/WSL. Lock impede duas aquisições no mesmo diretório.
    import fcntl

    raw.mkdir(parents=True, exist_ok=True)
    journal = raw / "_acquisition"
    journal.mkdir(exist_ok=True)
    records = []
    with (raw / ".download.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for remote in files:
            relative = PurePosixPath(remote)
            if relative.is_absolute() or ".." in relative.parts or "\\" in remote or not relative.parts:
                raise ValueError("Nome remoto deve ser um caminho relativo seguro")
            destination = raw / remote
            if not destination.resolve().is_relative_to(raw.resolve()):
                raise ValueError("Destino fora da RAW")
            record_path = journal / (hashlib.sha256(remote.encode()).hexdigest() + ".json")
            if destination.exists():
                if not record_path.exists():
                    raise RuntimeError(f"Origem existente sem manifesto: {remote}; não será sobrescrita")
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if (record.get("competition") != COMPETITION or record.get("remote") != remote
                        or record.get("sha256") != sha256(destination)):
                    raise RuntimeError(f"Checksum/identidade divergente: {remote}; origem preservada")
                record["status"] = "complete"
                _write_record(record_path, record)
                records.append(record)
                continue
            with tempfile.TemporaryDirectory(prefix=".download-", dir=raw) as temp:
                stage = Path(temp)
                fetch(remote, stage)
                payload = _payload(stage, remote)
                if payload.stat().st_size == 0:
                    raise RuntimeError(f"Download vazio: {remote}")
                record = {
                    "competition": COMPETITION, "remote": remote,
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "sha256": sha256(payload), "bytes": payload.stat().st_size,
                    "status": "prepared",
                }
                _write_record(record_path, record)
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Hard link no mesmo filesystem publica sem sobrescrever destino existente.
                os.link(payload, destination)
                record["status"] = "complete"
                _write_record(record_path, record)
                records.append(record)
        fcntl.flock(lock, fcntl.LOCK_UN)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Lista arquivos sem acessar a API")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({"competition": COMPETITION, "files": FILES}, indent=2))
        return
    raw = load_paths(Path(__file__).resolve().parents[2])["raw_dir"]
    try:
        records = download_selected(raw)
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"ERRO: {exc}\n")
    print(json.dumps({"files_verified": len(records), "total_bytes": sum(r["bytes"] for r in records)}, indent=2))


if __name__ == "__main__":
    main()
