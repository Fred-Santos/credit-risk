from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json
import time

from pyspark.sql import SparkSession


def _mtime_utc_iso(p: Path) -> str:
    st = p.stat()
    return datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()


def _read_table(spark: SparkSession, p: Path):
    suf = p.suffix.lower()
    if suf == ".parquet":
        return spark.read.parquet(str(p))
    if suf == ".csv":
        return spark.read.option("header", "true").option("inferSchema", "true").csv(str(p))
    return None


def _estimate_row_count(df, sample_fraction: float = 0.02, sample_cap: int = 200_000) -> Optional[int]:
    if df is None:
        return None
    if df.limit(1).count() == 0:
        return 0
    sample = df.sample(withReplacement=False, fraction=sample_fraction, seed=42).limit(sample_cap)
    k = sample.count()
    if k == 0:
        return None
    return int(round(k / max(sample_fraction, 1e-9)))


def _diff_metrics(prev: Dict, cur: Dict, bytes_drop_threshold_pct: float = 30.0) -> Dict:
    alerts = []

    prev_files = {f["path"]: f for f in prev.get("files", [])}
    cur_files = {f["path"]: f for f in cur.get("files", [])}

    missing = sorted(set(prev_files.keys()) - set(cur_files.keys()))
    added = sorted(set(cur_files.keys()) - set(prev_files.keys()))

    if missing:
        alerts.append({"type": "missing_files", "severity": "fail", "count": len(missing), "examples": missing[:20]})
    if added:
        alerts.append({"type": "new_files", "severity": "warn", "count": len(added), "examples": added[:20]})

    prev_total = prev.get("total_bytes")
    cur_total = cur.get("total_bytes")
    if isinstance(prev_total, int) and isinstance(cur_total, int) and prev_total > 0:
        drop_pct = (prev_total - cur_total) / prev_total * 100.0
        if drop_pct >= bytes_drop_threshold_pct:
            alerts.append({
                "type": "total_bytes_drop",
                "severity": "warn",
                "prev_total_bytes": prev_total,
                "cur_total_bytes": cur_total,
                "drop_pct": round(drop_pct, 2),
                "threshold_pct": bytes_drop_threshold_pct,
            })

    return {"alerts": alerts, "missing_files": missing, "new_files": added}


def record_raw_metrics(
    ctx,
    spark: Optional[SparkSession] = None,
    include_row_estimates: bool = True,
    sample_fraction: float = 0.02,
    max_tables_for_row_estimates: int = 50,
):
    out_dir = ctx.repo_root / "docs" / "observability" / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_path = out_dir / "latest_raw_metrics.json"
    t0 = time.time()

    files = sorted([p for p in ctx.raw_dir.rglob("*") if p.is_file()])
    total_bytes = sum(p.stat().st_size for p in files)

    file_entries = [
        {"path": p.relative_to(ctx.repo_root).as_posix(), "bytes": p.stat().st_size, "mtime_utc": _mtime_utc_iso(p)}
        for p in files
    ]

    table_files = [p for p in files if p.suffix.lower() in (".parquet", ".csv")]
    do_rows = bool(include_row_estimates and spark is not None)

    table_entries = []
    for i, p in enumerate(table_files):
        rel = p.relative_to(ctx.repo_root).as_posix()
        entry = {"path": rel, "format": p.suffix.lower().lstrip(".")}

        if do_rows and i < max_tables_for_row_estimates:
            df = _read_table(spark, p)
            entry["row_count_estimate"] = _estimate_row_count(df, sample_fraction=sample_fraction)
        else:
            entry["row_count_estimate"] = None

        table_entries.append(entry)

    cur = {
        "run_id": ctx.run_id,
        "started_at_utc": ctx.started_at_utc,
        "raw_dir": ctx.raw_dir.relative_to(ctx.repo_root).as_posix(),
        "duration_seconds": round(time.time() - t0, 3),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": file_entries,
        "tables": table_entries,
        "row_estimates": {
            "enabled": do_rows,
            "sample_fraction": sample_fraction if do_rows else None,
            "max_tables": max_tables_for_row_estimates if do_rows else 0,
        },
    }

    out_json = out_dir / f"{ctx.run_id}_raw_metrics.json"
    out_json.write_text(json.dumps(cur, indent=2), encoding="utf-8")

    prev = None
    if latest_path.exists():
        try:
            prev = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            prev = None

    # atualiza latest sempre
    latest_path.write_text(json.dumps(cur, indent=2), encoding="utf-8")

    alerts_out = None
    if prev:
        diff = _diff_metrics(prev, cur)
        alerts_out = out_dir / f"{ctx.run_id}_raw_alerts.json"
        alerts_out.write_text(json.dumps({"run_id": ctx.run_id, **diff}, indent=2), encoding="utf-8")

    return {"json": str(out_json), "latest": str(latest_path), "alerts": str(alerts_out) if alerts_out else None}
