from __future__ import annotations

import sys
from pathlib import Path

from pyspark.sql import SparkSession

from src.utils.run_context import RunContext
from src.profiling.data_dictionary_raw import generate_data_dictionary
from src.quality.checks_raw import run_raw_checks
from src.observability.metrics_raw import record_raw_metrics
from src.lineage.lineage_raw import emit_raw_lineage
from src.governance.inventory_raw import build_datasets_inventory


def main():
    repo_root = Path(__file__).resolve().parents[2]
    ctx = RunContext.create(repo_root)

    if not ctx.raw_dir.exists():
        raise RuntimeError(f"Raw dir não existe: {ctx.raw_dir}")

    spark = (
        SparkSession.builder
        .appName("credit-risk-raw-mvp")
        .master("local[*]")
        .getOrCreate()
    )

    try:
        generate_data_dictionary(ctx, spark)
        run_raw_checks(ctx, spark)
        record_raw_metrics(ctx, spark=spark, include_row_estimates=True)
        emit_raw_lineage(ctx, include_checksums=True, checksum_max_files=200)
        build_datasets_inventory(ctx)
    finally:
        spark.stop()


    print(f"OK: Raw MVP gerado. Run ID: {ctx.run_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelado pelo usuário.")
        sys.exit(130)
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
