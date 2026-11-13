"""Prova Spark/Delta com dois registros sintéticos; não substitui Home Credit."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import tempfile
import time

from src.utils.spark import create_spark_session


def check_environment(repo_root: Path) -> dict:
    from delta.tables import DeltaTable

    started = time.perf_counter()
    temporary_root = repo_root / ".runtime" / "tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credit-risk-smoke-", dir=temporary_root) as temp:
        path = str(Path(temp) / "casos")
        spark = create_spark_session(repo_root, app_name="credit-risk-environment", delta=True)
        try:
            initial = spark.createDataFrame([(101, 0), (102, 1)], "case_id long, target int")
            initial.write.format("delta").save(path)
            correction = spark.createDataFrame([(101, 1)], "case_id long, target int")
            (DeltaTable.forPath(spark, path).alias("t").merge(correction.alias("s"), "t.case_id = s.case_id")
             .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
            current = spark.read.format("delta").load(path)
            previous = spark.read.format("delta").option("versionAsOf", 0).load(path)
            actual = sorted((r.case_id, r.target) for r in current.collect())
            historical = sorted((r.case_id, r.target) for r in previous.collect())
            if actual != [(101, 1), (102, 1)] or historical != [(101, 0), (102, 1)]:
                raise RuntimeError("Prova Delta não produziu o conteúdo esperado")
            result = {
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "data_kind": "synthetic_test_only", "status": "passed",
                "python": platform.python_version(), "spark": spark.version,
                "delta_spark": version("delta-spark"),
                "java": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
                "master": spark.sparkContext.master,
                "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
                "current": actual, "version_0": historical,
                "table_bytes": sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file()),
            }
        finally:
            spark.stop()
    result["duration_seconds"] = round(time.perf_counter() - started, 3)
    return result


def main():
    repo_root = Path(__file__).resolve().parents[2]
    result = check_environment(repo_root)
    output = repo_root / "artifacts" / "environment_check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
