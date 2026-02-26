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
    if p.suffix.lower() == ".parquet":
        return spark.read.parquet(str(p))
    if p.suffix.lower() == ".csv":
        return spark.read.option("header", "true").option("inferSchema", "true").csv(str(p))
    return None


def record_bronze_metrics(
    ctx,
    spark: Optional[SparkSession] = None,
    include_row_counts: bool = True,
):
    bronze_dir = ctx.repo_root / "data" / "bronze"
    outdir = ctx.repo_root / "docs" / "observability" / "metrics"
    outdir.mkdir(parents=True, exist_ok=True)

    latestpath = outdir / "latest_bronze_metrics.json"
    t0 = time.time()

    files = sorted([p for p in bronze_dir.rglob("*") if p.is_file()])
    totalbytes = sum(p.stat().st_size for p in files)

    fileentries = [{"path": p.relative_to(ctx.repo_root).as_posix(), "bytes": p.stat().st_size, "mtime_utc": _mtime_utc_iso(p)} for p in files]

    tablefiles = [p for p in files if p.suffix.lower() in (".parquet", ".csv")]
    tableentries = []

    for p in tablefiles:
        rel = p.relative_to(ctx.repo_root).as_posix()
        entry = {"path": rel, "format": p.suffix.lower().lstrip(".")}

        if include_row_counts and spark is not None:
            df = _read_table(spark, p)
            entry["row_count"] = int(df.count()) if df is not None else None
            entry["columns"] = len(df.columns) if df is not None else None
        else:
            entry["row_count"] = None
            entry["columns"] = None

        tableentries.append(entry)

    cur = {
        "runid": ctx.run_id,
        "started_at_utc": ctx.started_at_utc,
        "bronze_dir": bronze_dir.relative_to(ctx.repo_root).as_posix(),
        "duration_seconds": round(time.time() - t0, 3),
        "file_count": len(files),
        "total_bytes": totalbytes,
        "files": fileentries,
        "tables": tableentries,
        "row_counts": {"enabled": bool(include_row_counts and spark is not None)},
    }

    outjson = outdir / f"{ctx.run_id}_bronze_metrics.json"
    outjson.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    latestpath.write_text(json.dumps(cur, indent=2), encoding="utf-8")

    return {"json": str(outjson), "latest": str(latestpath)}

