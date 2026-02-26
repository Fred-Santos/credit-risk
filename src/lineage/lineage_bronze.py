from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, chunksize: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunksize), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_git_commit(reporoot: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(reporoot),
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return None


def _list_files(root: Path) -> List[Path]:
    return sorted([p for p in root.rglob("*") if p.is_file()])


def emit_bronze_lineage(ctx, include_checksums: bool = True, checksum_max_files: int = 200):
    out_events = ctx.repo_root / "docs" / "lineage" / "lineage_events"
    out_events.mkdir(parents=True, exist_ok=True)

    out_md = ctx.repo_root / "docs" / "lineage" / "dataset_lineage.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    raw_train = ctx.raw_dir / "parquet_files" / "train"
    bronze_dir = ctx.repo_root / "data" / "bronze"

    gitcommit = _try_git_commit(ctx.repo_root)

    bronze_files = _list_files(bronze_dir)

    fileentries = []
    for i, p in enumerate(bronze_files):
        stat = p.stat()
        entry = {
            "path": p.relative_to(ctx.repo_root).as_posix(),
            "bytes": stat.st_size,
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
        if include_checksums and i < checksum_max_files:
            entry["sha256"] = _sha256_file(p)
        fileentries.append(entry)

    event = {
        "eventType": "COMPLETE",
        "eventTime": _utcnow_iso(),
        "run": {"runId": ctx.run_id, "startedAt": ctx.started_at_utc},
        "facets": {
            "git": {"commit": gitcommit} if gitcommit else {},
            "runtime": {"python": os.sys.version.split()[0], "platform": os.name},
        },
        "job": {"namespace": "local", "name": "bronze_mvp"},
        "inputs": [
            {"namespace": "file", "name": raw_train.relative_to(ctx.repo_root).as_posix()},
        ],
        "outputs": [
            {"namespace": "file", "name": bronze_dir.relative_to(ctx.repo_root).as_posix()},
        ],
        "artifacts": {
            "bronzeFiles": {
                "count": len(bronze_files),
                "checksumsIncluded": bool(include_checksums),
                "checksumMaxFiles": int(checksum_max_files),
                "files": fileentries,
            }
        },
    }

    outjson = out_events / f"{ctx.run_id}_bronze_lineage.json"
    outjson.write_text(json.dumps(event, indent=2), encoding="utf-8")

    mdlines = []
    mdlines.append("## Dataset lineage BRONZE")
    mdlines.append(f"- Run ID: {ctx.run_id}")
    mdlines.append(f"- Started UTC: {ctx.started_at_utc}")
    if gitcommit:
        mdlines.append(f"- Git commit: {gitcommit}")
    mdlines.append("")
    mdlines.append("### Fluxo")
    mdlines.append(f"- Input: {raw_train.relative_to(ctx.repo_root).as_posix()}")
    mdlines.append(f"- Output: {bronze_dir.relative_to(ctx.repo_root).as_posix()}")
    mdlines.append("")
    mdlines.append("### Artefatos")
    mdlines.append(f"- JSON do evento: docs/lineage/lineage_events/{outjson.name}")
    mdlines.append(f"- Arquivos em bronze: {len(bronze_files)}")
    mdlines.append("")
    mdlines.append("### Lista top 50")
    for e in fileentries[:50]:
        mdlines.append(f"- {e['path']} ({e['bytes']} bytes)")
    if len(fileentries) > 50:
        mdlines.append(f"- ... {len(fileentries) - 50} arquivos")

    # Append/overwrite? Para manter igual seu RAW (overwrite), vamos sobrescrever seÃ§Ã£o Bronze inteira:
    # Simples: concatena no final do arquivo (para nÃ£o destruir RAW).
    existing = out_md.read_text(encoding="utf-8") if out_md.exists() else ""
    updated = (existing.strip() + "\n\n" + "\n".join(mdlines) + "\n").lstrip("\n")
    out_md.write_text(updated, encoding="utf-8")

    return {"json": str(outjson), "md": str(out_md)}

