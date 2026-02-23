from __future__ import annotations

from pathlib import Path
import json
import fnmatch

import yaml
from pyspark.sql import SparkSession


def _read_any_table(spark: SparkSession, p: Path):
    if p.suffix.lower() == ".parquet":
        return spark.read.parquet(str(p))
    return spark.read.option("header", "true").option("inferSchema", "true").csv(str(p))


def _load_rules(repo_root: Path) -> dict:
    p = repo_root / "configs" / "quality_rules.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _match_table_rules(rules: dict, rel_from_raw: str) -> list:
    matched = []
    for t in rules.get("tables", []):
        pat = t.get("pattern")
        if pat and fnmatch.fnmatch(rel_from_raw.replace("\\", "/"), pat):
            matched.extend(t.get("checks", []))
    return matched


def run_raw_checks(ctx, spark: SparkSession):
    results_dir = ctx.repo_root / "docs" / "data_quality" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    rules = _load_rules(ctx.repo_root)
    defaults = rules.get("defaults", {})
    default_action = defaults.get("action_on_fail", "fail")

    tables = sorted([p for p in ctx.raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".parquet", ".csv")])

    results = []
    failed = 0

    for p in tables:
        rel_raw = p.relative_to(ctx.raw_dir).as_posix()
        checks = _match_table_rules(rules, rel_raw)

        if not checks:
            continue  # sem regra para essa tabela

        df = _read_any_table(spark, p)

        for chk in checks:
            ctype = chk.get("type")
            severity = chk.get("severity", default_action)

            if ctype == "non_empty":
                ok = df.limit(1).count() > 0
                results.append({"table": rel_raw, "check": "non_empty", "severity": severity, "success": bool(ok)})
                if not ok and severity == "fail":
                    failed += 1

            elif ctype == "require_columns":
                required = chk.get("columns", [])
                missing = [c for c in required if c not in df.columns]
                ok = len(missing) == 0
                results.append({
                    "table": rel_raw,
                    "check": "require_columns",
                    "severity": severity,
                    "success": bool(ok),
                    "missing_columns": missing,
                })
                if not ok and severity == "fail":
                    failed += 1

            else:
                results.append({"table": rel_raw, "check": ctype, "severity": severity, "success": False, "error": "unknown_check"})
                if severity == "fail":
                    failed += 1

    payload = {
        "run_id": ctx.run_id,
        "started_at_utc": ctx.started_at_utc,
        "failed_checks": failed,
        "results": results,
    }

    out_json = results_dir / f"{ctx.run_id}_raw_checks.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Decide ação
    if failed > 0 and default_action == "fail":
        raise RuntimeError(f"Data Quality falhou: {failed} checks severidade=fail")

    return {"json": str(out_json), "failed_checks": failed}
