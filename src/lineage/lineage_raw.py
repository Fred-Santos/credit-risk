from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    # checksum SHA-256 por streaming (não carrega o arquivo todo na memória). [web:415]
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_git_commit(repo_root: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return None


def _list_data_files(raw_dir: Path) -> List[Path]:
    return sorted([p for p in raw_dir.rglob("*") if p.is_file()])


def emit_raw_lineage(ctx, include_checksums: bool = True, checksum_max_files: int = 200):
    """
    Gera:
      - docs/lineage/lineage_events/<run_id>_raw_lineage.json
      - docs/lineage/dataset_lineage.md  (atualiza/overwrite com o run atual)

    O foco aqui é:
      - de onde veio (input: Kaggle)
      - o que foi materializado (outputs: arquivos em data/raw)
      - como reproduzir/auditar (run_id, timestamps, git commit, tamanhos, hashes)
    """
    out_events = ctx.repo_root / "docs" / "lineage" / "lineage_events"
    out_events.mkdir(parents=True, exist_ok=True)

    out_md = ctx.repo_root / "docs" / "lineage" / "dataset_lineage.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    git_commit = _try_git_commit(ctx.repo_root)
    files = _list_data_files(ctx.raw_dir)

    # Metadados por arquivo (sem schema/dtypes)
    file_entries: List[Dict] = []
    for i, p in enumerate(files):
        stat = p.stat()
        entry = {
            "path": p.relative_to(ctx.repo_root).as_posix(),
            "bytes": stat.st_size,
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

        # checksums podem ser caros; limite para não ficar lento
        if include_checksums and i < checksum_max_files:
            entry["sha256"] = _sha256_file(p)

        file_entries.append(entry)

    event = {
        "eventType": "COMPLETE",
        "eventTime": _utc_now_iso(),
        "run": {
            "runId": ctx.run_id,
            "startedAt": ctx.started_at_utc,
            "facets": {
                "git": {"commit": git_commit} if git_commit else {},
                "runtime": {
                    "python": sys.version.split()[0] if "sys" in globals() else None,
                    "platform": os.name,
                },
            },
        },
        "job": {
            "namespace": "local",
            "name": "raw_mvp",
            "facets": {
                "documentation": {
                    "description": "Ingestão e governança RAW (download/unzip/limpeza + profiling/quality/metrics/lineage).",
                    "contentType": "text/plain",
                }
            },
        },
        "inputs": [
            {
                "namespace": "kaggle",
                "name": "home-credit-credit-risk-model-stability",
                "facets": {
                    "documentation": {
                        "description": "Fonte: Kaggle competition dataset (download via kaggle CLI/API).",
                        "contentType": "text/plain",
                    }
                },
            }
        ],
        "outputs": [
            {
                "namespace": "file",
                "name": ctx.raw_dir.as_posix(),
                "facets": {
                    "dataQuality": {
                        "note": "Qualidade detalhada registrada separadamente em docs/data_quality/results/.",
                    },
                    "storage": {"format": "mixed (parquet/csv)", "path": ctx.raw_dir.as_posix()},
                },
            }
        ],
        "artifacts": {
            "raw_files": {
                "count": len(files),
                "checksum_included": bool(include_checksums),
                "checksum_max_files": checksum_max_files,
                "files": file_entries,
            }
        },
    }

    out_json = out_events / f"{ctx.run_id}_raw_lineage.json"
    out_json.write_text(json.dumps(event, indent=2), encoding="utf-8")

    # Markdown simples e “humano”
    md_lines = []
    md_lines.append("# Dataset lineage (RAW)\n")
    md_lines.append(f"- Run ID: {ctx.run_id}\n")
    md_lines.append(f"- Started (UTC): {ctx.started_at_utc}\n")
    if git_commit:
        md_lines.append(f"- Git commit: `{git_commit}`\n")
    md_lines.append("\n## Fluxo\n")
    md_lines.append("- **Input:** kaggle://home-credit-credit-risk-model-stability\n")
    md_lines.append(f"- **Output (raw):** `{ctx.raw_dir.relative_to(ctx.repo_root).as_posix()}`\n")
    md_lines.append("\n## Artefatos\n")
    md_lines.append(f"- JSON do evento: `docs/lineage/lineage_events/{out_json.name}`\n")
    md_lines.append(f"- Arquivos em raw: {len(files)}\n")
    md_lines.append("\n## Lista (top 50)\n")
    for p in file_entries[:50]:
        md_lines.append(f"- `{p['path']}` ({p['bytes']} bytes)")
    if len(file_entries) > 50:
        md_lines.append(f"- ... ({len(file_entries) - 50} arquivos)")

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {"json": str(out_json), "md": str(out_md)}

