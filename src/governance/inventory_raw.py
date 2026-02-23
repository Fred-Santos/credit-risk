from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import csv


def _find_feature_definitions(raw_dir: Path) -> Optional[Path]:
    # tenta no raw root primeiro e depois em subpastas
    cands = list(raw_dir.rglob("feature_definitions.csv"))
    return cands[0] if cands else None


def _load_feature_definitions(p: Path) -> Dict[str, str]:
    """
    Esperado: colunas Variable, Description (como no seu lineage anterior). [file:410]
    """
    mapping: Dict[str, str] = {}
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            var = (row.get("Variable") or "").strip()
            desc = (row.get("Description") or "").strip()
            if var:
                mapping[var] = desc
    return mapping


def build_datasets_inventory(ctx) -> str:
    out_path = ctx.repo_root / "docs" / "governance" / "datasets_inventory.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    feat_path = _find_feature_definitions(ctx.raw_dir)
    feat_map = _load_feature_definitions(feat_path) if feat_path else {}

    tables = sorted([p for p in ctx.raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".parquet", ".csv")])

    lines: List[str] = []
    lines.append("# Datasets inventory (RAW)\n")
    lines.append(f"- Run ID: {ctx.run_id}\n")
    lines.append(f"- Raw dir: `{ctx.raw_dir.relative_to(ctx.repo_root).as_posix()}`\n")
    lines.append("\n## Convenções\n")
    lines.append("- Owner: **TBD** (definir responsável)\n")
    lines.append("- Classificação/PII: **TBD** (definir política)\n")
    lines.append("\n## Tabelas\n")
    lines.append("| dataset | tipo | owner | classificação | descrição |")
    lines.append("|---|---|---|---|---|")

    for p in tables:
        rel = p.relative_to(ctx.raw_dir).as_posix()
        typ = p.suffix.lower().lstrip(".")
        owner = "TBD"
        classification = "TBD"
        desc = ""

        # se for o próprio feature_definitions.csv, documenta
        if p.name.lower() == "feature_definitions.csv":
            desc = "Dicionário oficial de variáveis (Variable, Description)."
        elif p.suffix.lower() == ".parquet":
            desc = "Tabela raw (parquet) baixada da competição."
        else:
            desc = "Tabela raw (csv) baixada da competição."

        lines.append(f"| `{rel}` | {typ} | {owner} | {classification} | {desc} |")

    if feat_path:
        lines.append("\n## Feature definitions\n")
        lines.append(f"- Fonte: `{feat_path.relative_to(ctx.repo_root).as_posix()}`\n")
        lines.append(f"- Variáveis descritas: {len(feat_map)}\n")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out_path)
