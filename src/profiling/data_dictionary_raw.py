from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from pyspark.sql import SparkSession, functions as F


def _df_is_empty(df) -> bool:
    # Spark recente: df.isEmpty() [web:378]
    if hasattr(df, "isEmpty"):
        return df.isEmpty()
    return df.limit(1).count() == 0


def _read_any_table(spark: SparkSession, path: Path):
    suf = path.suffix.lower()
    if suf == ".parquet":
        return spark.read.parquet(str(path))
    if suf == ".csv":
        return (
            spark.read.option("header", "true")
            .option("inferSchema", "true")
            .csv(str(path))
        )
    raise ValueError(f"Formato não suportado: {path}")


def _profile_df(df, max_examples=5):
    dtypes = dict(df.dtypes)

    if _df_is_empty(df):
        return 0, [
            {"column": c, "dtype": dtypes.get(c, ""), "null_pct": 0.0, "approx_nunique": 0, "examples": []}
            for c in df.columns
        ]

    total = df.count()

    exprs = []
    for c in df.columns:
        null_expr = F.coalesce(
            F.sum(F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0))),
            F.lit(0)
        ).cast("long").alias(f"__nulls__{c}")

        adist_expr = F.coalesce(
            F.approx_count_distinct(F.col(c)),
            F.lit(0)
        ).cast("long").alias(f"__adist__{c}")

        exprs.append(null_expr)
        exprs.append(adist_expr)

    agg = df.agg(*exprs).collect()[0].asDict()

    rows = []
    for c in df.columns:
        nulls_val = agg.get(f"__nulls__{c}")
        adist_val = agg.get(f"__adist__{c}")

        nulls = int(nulls_val) if nulls_val is not None else 0
        adist = int(adist_val) if adist_val is not None else 0
        null_pct = round((nulls / total * 100.0), 2) if total else 0.0

        ex_rows = (
            df.select(F.col(c).cast("string").alias(c))
              .where(F.col(c).isNotNull())
              .dropDuplicates([c])
              .limit(max_examples)
              .collect()
        )
        examples = [r[c] for r in ex_rows if r[c] is not None]

        rows.append(
            {"column": c, "dtype": dtypes.get(c, ""), "null_pct": null_pct, "approx_nunique": adist, "examples": examples}
        )

    return total, rows


def generate_data_dictionary(ctx, spark: SparkSession) -> Dict[str, str]:
    out_dir = ctx.repo_root / "docs" / "data_dictionary" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        [p for p in ctx.raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".parquet", ".csv")]
    )

    written: Dict[str, str] = {}
    for p in candidates:
        rel = p.relative_to(ctx.raw_dir).as_posix()
        print(f"[dictionary] profiling: {rel}")

        df = _read_any_table(spark, p)
        nrows, prof = _profile_df(df)
        ncols = len(df.columns)

        md_name = rel.replace("/", "__").replace("\\", "__")
        md_name = md_name.replace(".parquet", "").replace(".csv", "") + ".md"
        out_path = out_dir / md_name

        lines = []
        lines.append(f"# {rel}\n")
        lines.append(f"- Run ID: {ctx.run_id}\n")
        lines.append(f"- Linhas: {nrows}\n")
        lines.append(f"- Colunas: {ncols}\n")
        lines.append("\n## Colunas\n")
        lines.append("| column | dtype | null_pct | approx_nunique | examples |")
        lines.append("|---|---|---:|---:|---|")

        for r in sorted(prof, key=lambda x: x["column"]):
            ex = ", ".join([str(v).replace("|", "\\|").replace("\n", " ") for v in r["examples"]])
            lines.append(f"| {r['column']} | {r['dtype']} | {r['null_pct']} | {r['approx_nunique']} | {ex} |")

        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written[rel] = str(out_path.relative_to(ctx.repo_root)).replace("\\", "/")

    index = out_dir.parent / "README.md"
    idx_lines = [f"# Data Dictionary (raw)\n", f"- Run ID: {ctx.run_id}\n", ""]
    for rel, md in sorted(written.items()):
        idx_lines.append(f"- `{rel}` → [{Path(md).name}](tables/{Path(md).name})")
    index.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    return written
