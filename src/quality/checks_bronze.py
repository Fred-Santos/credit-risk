from __future__ import annotations

from pathlib import Path
import fnmatch
import json
import yaml

from pyspark.sql import SparkSession


def _read_any_table(spark: SparkSession, p: Path):
    if p.suffix.lower() == ".parquet":
        return spark.read.parquet(str(p))
    if p.suffix.lower() == ".csv":
        return spark.read.option("header", "true").option("inferSchema", "true").csv(str(p))
    return None


def _load_rules(reporoot: Path) -> dict:
    p = reporoot / "configs" / "quality_rules_bronze.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _match_table_rules(rules: dict, rel_from_bronze: str) -> list:
    matched = []
    for t in rules.get("tables", []):
        pat = t.get("pattern")
        if pat and fnmatch.fnmatch(rel_from_bronze.replace("\\", "/"), pat):
            matched.extend(t.get("checks", []))
    return matched


def run_bronze_checks(ctx, spark: SparkSession):
    resultsdir = ctx.repo_root / "docs" / "data_quality" / "bronze_results"
    resultsdir.mkdir(parents=True, exist_ok=True)

    bronze_dir = ctx.repo_root / "data" / "bronze"
    rules = _load_rules(ctx.repo_root)
    defaults = rules.get("defaults", {})
    default_action = defaults.get("action_on_fail", "warn")

    tables = sorted([p for p in bronze_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".parquet", ".csv")])

    results = []
    failed = 0

    for p in tables:
        rel = p.relative_to(bronze_dir).as_posix()
        checks = _match_table_rules(rules, rel)
        if not checks:
            continue

        df = _read_any_table(spark, p)
        for chk in checks:
            ctype = chk.get("type")
            severity = chk.get("severity", default_action)

            if ctype == "nonempty":
                ok = df.limit(1).count() > 0
                results.append({"table": rel, "check": "nonempty", "severity": severity, "success": bool(ok)})
                if (not ok) and severity == "fail":
                    failed += 1

            elif ctype == "require_columns":
                required = chk.get("columns", [])
                missing = [c for c in required if c not in df.columns]
                ok = len(missing) == 0
                results.append({
                    "table": rel,
                    "check": "require_columns",
                    "severity": severity,
                    "success": bool(ok),
                    "missing_columns": missing
                })
                if (not ok) and severity == "fail":
                    failed += 1

            else:
                results.append({"table": rel, "check": ctype, "severity": severity, "success": False, "error": "unknown_check"})
                if severity == "fail":
                    failed += 1

    payload = {
        "runid": ctx.run_id,
        "started_at_utc": ctx.started_at_utc,
        "failed_checks": failed,
        "results": results
    }

    outjson = resultsdir / f"{ctx.run_id}_bronze_checks.json"
    outjson.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if failed > 0 and default_action == "fail":
        raise RuntimeError(f"Data Quality (BRONZE) falhou: {failed} checks severidade=fail")

    return {"json": str(outjson), "failed_checks": failed}

