from __future__ import annotations

import sys
from pathlib import Path

from pyspark.sql import SparkSession

from src.utils.run_context import RunContext
from src.bronze.build_bronze import build_bronze_from_raw
from src.quality.checks_bronze import run_bronze_checks
from src.observability.metrics_bronze import record_bronze_metrics
from src.lineage.lineage_bronze import emit_bronze_lineage
from src.governance.inventory_bronze import build_bronze_inventory


def _bronze_has_parquet(repo_root: Path) -> bool:
    bronze_dir = repo_root / "data" / "bronze"
    if not bronze_dir.exists():
        return False
    return any(bronze_dir.rglob("*.parquet"))


def main():
    repo_root = Path(__file__).resolve().parents[2]
    ctx = RunContext.create(repo_root)

    raw_train = ctx.raw_dir / "parquet_files" / "train"
    if not raw_train.exists():
        raise RuntimeError(f"RAW train dir não existe: {raw_train}")

    # Perfil “8GB friendly”
    spark = (
        SparkSession.builder
        .appName("credit-risk-bronze-mvp")
        .master("local[1]")
        .config("spark.driver.memory", "4g")          # se der falta de RAM no Windows, volte para 3g
        .config("spark.driver.maxResultSize", "256m")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.sql.files.maxPartitionBytes", "67108864")  # 64MB
        .getOrCreate()
    )


    # (Opcional) diminuir verbosidade
    spark.sparkContext.setLogLevel("WARN")

    try:
        # 1) MATERIALIZA BRONZE (o build já faz chunking e coalesce)
        written = build_bronze_from_raw(ctx, spark)

        if not _bronze_has_parquet(ctx.repo_root):
            raise RuntimeError(
                "Bronze continua vazia após build_bronze_from_raw(). "
                "Verifique o layout de data/raw/parquet_files/train e os paths."
            )

        if written:
            print("Bronze materializada (paths):")
            for p in written[:50]:
                print(f"- {p}")
            if len(written) > 50:
                print(f"- ... {len(written) - 50} paths")

        # 2) GOVERNANÇA / OBS (cuidado: métricas com count podem ser pesadas)
        run_bronze_checks(ctx, spark)
        record_bronze_metrics(ctx, spark=spark, include_row_counts=False)  # <- 8GB safe
        emit_bronze_lineage(ctx, include_checksums=False)  # <- 8GB safe (hash é caro)
        build_bronze_inventory(ctx)

        print(f"OK Bronze MVP gerado. Run ID: {ctx.run_id}")

    finally:
        spark.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelado pelo usuário.")
        sys.exit(130)
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
