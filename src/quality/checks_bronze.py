from src.quality.engine import run_checks


def run_bronze_checks(ctx, spark):
    return run_checks(ctx, spark, layer="bronze")
