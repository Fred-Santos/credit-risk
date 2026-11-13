"""Profiling exato compartilhado por inspeção e contratos."""
from functools import reduce


def profile_frame(df, key: list[str]) -> dict:
    from pyspark.sql import functions as F

    missing = set(key + ["case_id"]) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(missing)}")
    null_condition = reduce(lambda a, b: a | b, [F.col(c).isNull() for c in key])
    expressions = [F.count("*").alias("rows"),
                   F.sum(null_condition.cast("long")).alias("null_key_rows")]
    for index, field in enumerate(df.schema.fields):
        expressions.append(F.sum(F.col(field.name).isNull().cast("long")).alias(f"null_{index}"))
        if field.dataType.simpleString() in {"float", "double"}:
            expressions.append(F.sum(F.isnan(field.name).cast("long")).alias(f"nan_{index}"))
    aggregate = df.agg(*expressions).first().asDict()
    duplicate = (df.groupBy(*key).count().filter(F.col("count") > 1)
                 .agg(F.count("*").alias("groups"),
                      F.sum(F.col("count") - 1).alias("excess_rows")).first())
    return {
        "rows": aggregate["rows"], "columns": len(df.columns), "key": key,
        "distinct_cases": df.select("case_id").where("case_id is not null").distinct().count(),
        "null_key_rows": aggregate["null_key_rows"] or 0,
        "duplicate_key_groups": duplicate["groups"],
        "duplicate_excess_rows": duplicate["excess_rows"] or 0,
        "schema": [{"column": field.name, "type": field.dataType.simpleString(),
                    "nullable_in_schema": field.nullable,
                    "null_count": aggregate[f"null_{index}"] or 0,
                    "nan_count": aggregate.get(f"nan_{index}", 0) or 0}
                   for index, field in enumerate(df.schema.fields)],
    }


def profile_base(df) -> dict:
    from pyspark.sql import functions as F

    dates = df.withColumn("_parsed_date", F.try_to_timestamp("date_decision", F.lit("yyyy-MM-dd")).cast("date"))
    aggregate = dates.agg(
        F.min("_parsed_date").alias("min_date"), F.max("_parsed_date").alias("max_date"),
        F.min("MONTH").alias("min_month"), F.max("MONTH").alias("max_month"),
        F.min("WEEK_NUM").alias("min_week"), F.max("WEEK_NUM").alias("max_week"),
        F.sum((F.col("date_decision").isNotNull() & F.col("_parsed_date").isNull()).cast("long")).alias("invalid_dates"),
        F.sum((F.col("MONTH") != F.date_format("_parsed_date", "yyyyMM").cast("long")).cast("long")).alias("month_mismatches"),
        F.sum((F.col("target").isNull() | ~F.col("target").isin(0, 1)).cast("long")).alias("invalid_targets"),
    ).first().asDict()
    aggregate["target_counts"] = [r.asDict() for r in df.groupBy("target").count().orderBy("target").collect()]
    aggregate["monthly_counts"] = [r.asDict() for r in df.groupBy("MONTH").count().orderBy("MONTH").collect()]
    aggregate["week_count"] = df.select("WEEK_NUM").distinct().count()
    return aggregate


