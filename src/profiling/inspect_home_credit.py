"""Inspeção exata do conjunto Home Credit selecionado, sem exportar registros."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import time

from src.pipelines.download_home_credit import sha256
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session
from src.profiling.frame_profile import profile_frame, profile_base
from src.quality.contracts import load_contract, read_source_frames, source_fingerprints



def inspect_source(ctx, spark) -> dict:
    started = time.perf_counter()
    contract = load_contract(ctx.repo_root / 'configs/contracts/home_credit_v1.yaml')
    source_fingerprints(ctx.raw_dir, contract)
    frames = read_source_frames(spark, ctx.raw_dir, contract)
    reports = {}
    for name, specification in contract['tables'].items():
        paths = [ctx.raw_dir / filename for filename in specification['files']]
        report = profile_frame(frames[name], specification["key"])
        report["files"] = [{"path": p.relative_to(ctx.raw_dir).as_posix(),
                            "bytes": p.stat().st_size, "sha256": sha256(p)} for p in paths]
        report["shard_schemas_equal"] = True
        reports[name] = report
        print(f"Inspecionado {name}: {report['rows']} linhas; {report['duplicate_key_groups']} grupos de chave duplicada", flush=True)
    base = frames["train_base"]
    base_keys = base.select("case_id").where("case_id is not null").distinct()
    base_report = profile_base(base)
    for name in ("train_static_0", "train_applprev_1"):
        keys = frames[name].select("case_id").where("case_id is not null").distinct()
        orphans = keys.join(base_keys, "case_id", "left_anti").count()
        uncovered = base_keys.join(keys, "case_id", "left_anti").count()
        reports[name]["orphan_cases"] = orphans
        reports[name]["base_cases_without_match"] = uncovered
        reports[name]["coverage"] = (
            (reports["train_base"]["distinct_cases"] - uncovered) / reports["train_base"]["distinct_cases"]
            if reports["train_base"]["distinct_cases"] else None)
    definitions_path = ctx.raw_dir / "feature_definitions.csv"
    with definitions_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["Variable", "Description"]:
            raise ValueError("Schema inesperado em feature_definitions.csv")
        definitions = list(reader)
    defined = {row["Variable"] for row in definitions}
    structural = {"case_id", "num_group1", "num_group2", "MONTH", "WEEK_NUM", "target", "date_decision"}
    for name, frame in frames.items():
        reports[name]["features_without_definition"] = sorted(set(frame.columns) - defined - structural)
    checks = {
        "tables_non_empty": all(r["rows"] > 0 for r in reports.values()),
        "keys_non_null": all(r["null_key_rows"] == 0 for r in reports.values()),
        "keys_unique_in_logical_tables": all(r["duplicate_key_groups"] == 0 for r in reports.values()),
        "no_orphan_cases": all(r.get("orphan_cases", 0) == 0 for r in reports.values()),
        "valid_dates": base_report["invalid_dates"] == 0,
        "month_matches_decision_date": base_report["month_mismatches"] == 0,
        "valid_target_domain": base_report["invalid_targets"] == 0,
    }
    return {
        "run_id": ctx.run_id, "started_at_utc": ctx.started_at_utc,
        "data_kind": "real_home_credit_selected_files", "tables": reports,
        "base": base_report, "definitions_rows": len(definitions),
        "checks": checks, "status": "passed" if all(checks.values()) else "failed",
        "duration_seconds": round(time.perf_counter() - started, 3),
    }


def main():
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    spark = create_spark_session(ctx.repo_root, app_name="credit-risk-source-inspection")
    try:
        report = inspect_source(ctx, spark)
    finally:
        spark.stop()
    output = ctx.repo_root / "artifacts" / "source_inspection" / f"{ctx.run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "status": report["status"], "checks": report["checks"]}, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
