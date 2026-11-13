from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
from contextlib import contextmanager
import hashlib
import json
import os
import shutil

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

    # Nested (mantém como estava)
    nested: Dict[str, List[str]] = {}
    for p in raw_train_dir.rglob("*.parquet"):
        if not p.is_file():
            continue
        rel = p.relative_to(raw_train_dir)
        if len(rel.parts) >= 2:
            ds = rel.parts[0]
            nested.setdefault(ds, []).append(str(p))

    groups = [(p.stem, [str(p)]) for p in flat]
    if set(nested) & {name for name, _ in groups}:
        raise RuntimeError("Nomes de datasets conflitantes no layout RAW")
    return sorted(groups + [(ds, sorted(files)) for ds, files in nested.items()])


@contextmanager
def _ingestion_lock(root: Path, name: str = ".ingestion.lock"):
    # O sistema operacional libera o lock inclusive se o processo morrer.
    with (root / name).open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _source_record(path: Path, raw_dir: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": path.relative_to(raw_dir).as_posix(), "sha256": digest.hexdigest()}


def _output_checksums(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*.parquet")):
        result[path.relative_to(root).as_posix()] = _source_record(path, root)["sha256"]
    return result



def build_bronze_from_raw(
    ctx,
    spark: SparkSession,
    *,
    max_files_per_read: int = 10,        # tamanho dos grupos; cada fonte é lida isoladamente
    write_coalesce: int = 1,             # arquivos de saída por fonte
    partition_by_ingest_date: bool = False,
    fail_fast_probe: bool = True,        # faz uma ação leve pra validar o read
) -> List[str]:
    raw_train_dir = ctx.ingestion_dir / "parquet_files" / "train"
    bronze_root = ctx.bronze_dir
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

    with _ingestion_lock(bronze_root):
        return _materialize(ctx, spark, inputs, bronze_root, max_files_per_read,
                            write_coalesce, partition_by_ingest_date, fail_fast_probe)


def _materialize(ctx, spark, inputs, bronze_root, max_files_per_read,
                 write_coalesce, partition_by_ingest_date, fail_fast_probe):
    written = []
    for dataset_name, files in inputs:
        out_path = bronze_root / dataset_name
        print(f"[DATASET] {dataset_name} -> {out_path} | arquivos: {len(files)}")

        # Dados anteriores não possuem identidade transacional confiável.
        if out_path.exists():
            if list(out_path.glob("*.parquet")) or list(out_path.glob("_ingest_date=*")):
                raise RuntimeError(
                    f"Bronze legada em {out_path}. Arquive a pasta e reconstrua a partir da RAW; "
                    "não é seguro acrescentar dados sem um manifesto de ingestão."
                )
        out_path.mkdir(parents=True, exist_ok=True)
        changed = False
        for chunk in _chunks(files, max_files_per_read):
            for filename in chunk:
                source = _source_record(Path(filename), ctx.ingestion_dir)
                # Identidade estável por caminho; mudanças de conteúdo exigem reconstrução.
                batch_id = hashlib.sha256(source["path"].encode()).hexdigest()
                destination = out_path / f"ingest_batch={batch_id}"
                if destination.exists():
                    manifest = destination / "_ingestion.json"
                    if not manifest.exists() or not list(destination.rglob("*.parquet")):
                        raise RuntimeError(f"Lote Bronze inválido: {destination}")
                    committed = json.loads(manifest.read_text(encoding="utf-8"))
                    if committed["source"] != source:
                        raise RuntimeError(f"Fonte RAW alterada: {source['path']}. Arquive e reconstrua o dataset Bronze.")
                    outputs = committed.get("output_files")
                    if not outputs or outputs != _output_checksums(destination):
                        raise RuntimeError(f"Saída Bronze alterada ou manifesto sem checksums: {destination}")
                    continue
                stage = bronze_root / ".staging" / dataset_name / batch_id
                shutil.rmtree(stage, ignore_errors=True)
                stage.parent.mkdir(parents=True, exist_ok=True)
                try:
                    df = spark.read.parquet(filename)
                    if fail_fast_probe:
                        df.limit(1).count()
                    df_bronze = _add_bronze_columns(df, ctx.run_id)
                    if write_coalesce and write_coalesce > 0:
                        df_bronze = df_bronze.coalesce(int(write_coalesce))
                    writer = df_bronze.write.mode("errorifexists")
                    if partition_by_ingest_date:
                        writer = writer.partitionBy("_ingest_date")
                    writer.parquet(str(stage))
                    if not any(stage.rglob("*.parquet")):
                        raise RuntimeError(f"Escrita Bronze não produziu Parquet: {filename}")
                    if _source_record(Path(filename), ctx.ingestion_dir) != source:
                        raise RuntimeError(f"Fonte modificada durante a leitura: {filename}")
                    (stage / "_ingestion.json").write_text(
                        json.dumps({"format_version": 2, "source": source, "run_id": ctx.run_id,
                                    "output_files": _output_checksums(stage)}, indent=2), encoding="utf-8")
                    # Rename no mesmo filesystem publica dados + manifesto juntos.
                    stage.rename(destination)
                    changed = True
                finally:
                    shutil.rmtree(stage, ignore_errors=True)
        if changed:
            written.append(out_path.relative_to(ctx.repo_root).as_posix())
    return written
