from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import current_date, input_file_name, lit


def _add_bronze_columns(df: DataFrame, run_id: str) -> DataFrame:
    return (
        df.withColumn("_run_id", lit(run_id))
          .withColumn("_ingest_date", current_date())
          .withColumn("_source_file", input_file_name())
    )


def _chunks(xs: List[str], size: int) -> List[List[str]]:
    if size <= 0:
        return [xs]
    return [xs[i:i + size] for i in range(0, len(xs), size)]


def _discover_inputs(raw_train_dir: Path) -> List[Tuple[str, List[str]]]:
    if not raw_train_dir.exists():
        return []

    # Flat: cada arquivo vira um dataset
    flat = sorted([p for p in raw_train_dir.glob("*.parquet") if p.is_file()])
    if flat:
        return [(p.stem, [str(p)]) for p in flat]

    # Nested (mantém como estava)
    nested: Dict[str, List[str]] = {}
    for p in raw_train_dir.rglob("*.parquet"):
        if not p.is_file():
            continue
        rel = p.relative_to(raw_train_dir)
        if len(rel.parts) >= 2:
            ds = rel.parts[0]
            nested.setdefault(ds, []).append(str(p))

    return [(ds, sorted(files)) for ds, files in sorted(nested.items())]



def build_bronze_from_raw(
    ctx,
    spark: SparkSession,
    *,
    max_files_per_read: int = 10,        # micro-chunks (8GB friendly)
    write_coalesce: int = 1,             # 1 arquivo por chunk (estável; depois você aumenta)
    partition_by_ingest_date: bool = False,
    fail_fast_probe: bool = True,        # faz uma ação leve pra validar o read
) -> List[str]:
    raw_train_dir = ctx.raw_dir / "parquet_files" / "train"
    bronze_root = ctx.repo_root / "data" / "bronze"
    bronze_root.mkdir(parents=True, exist_ok=True)

    inputs = _discover_inputs(raw_train_dir)

    print(f"RAW train dir: {raw_train_dir}")
    print(f"Grupos (datasets) encontrados: {len(inputs)}")
    for name, files in inputs[:20]:
        print(f"- {name}: {len(files)} parquet files")
    if len(inputs) > 20:
        print(f"- ... {len(inputs) - 20} grupos")

    if not inputs:
        raise RuntimeError(f"Nenhum parquet encontrado em: {raw_train_dir}")

    written: List[str] = []

    for dataset_name, files in inputs:
        out_path = bronze_root / dataset_name
        print(f"[DATASET] {dataset_name} -> {out_path} | arquivos: {len(files)}")

        # Importante: cria pasta (não escreve ainda), mas evita erro de path
        out_path.mkdir(parents=True, exist_ok=True)

        for i, file_chunk in enumerate(_chunks(files, max_files_per_read), start=1):
            print(f"  - chunk {i}: {len(file_chunk)} arquivos")

            df = spark.read.parquet(*file_chunk)

            # Ação leve para validar leitura e “falhar cedo”
            if fail_fast_probe:
                _ = df.limit(1).count()

            df_bronze = _add_bronze_columns(df, ctx.run_id)

            if write_coalesce and write_coalesce > 0:
                df_bronze = df_bronze.coalesce(int(write_coalesce))

            writer = df_bronze.write.mode("append")
            if partition_by_ingest_date:
                writer = writer.partitionBy("_ingest_date")

            writer.parquet(str(out_path))

        written.append(out_path.relative_to(ctx.repo_root).as_posix())

    return written
