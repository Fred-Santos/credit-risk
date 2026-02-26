from __future__ import annotations

from pathlib import Path
from typing import List


def build_bronze_inventory(ctx) -> str:
    bronze_dir = ctx.repo_root / "data" / "bronze"
    outpath = ctx.repo_root / "docs" / "governance" / "datasets_inventory_bronze.md"
    outpath.parent.mkdir(parents=True, exist_ok=True)

    tables = sorted([p for p in bronze_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".parquet", ".csv")])

    lines: List[str] = []
    lines.append("# Datasets inventory BRONZE")
    lines.append(f"- Run ID: {ctx.run_id}")
    lines.append(f"- Bronze dir: {bronze_dir.relative_to(ctx.repo_root).as_posix()}")
    lines.append("")
    lines.append("| dataset | tipo | path |")
    lines.append("|---|---|---|")

    for p in tables:
        rel = p.relative_to(bronze_dir).as_posix()
        typ = p.suffix.lower().lstrip(".")
        dataset = rel.split("/")[0] if "/" in rel else rel
        lines.append(f"| {dataset} | {typ} | {rel} |")

    outpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(outpath)

