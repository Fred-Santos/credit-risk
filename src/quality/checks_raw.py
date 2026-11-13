from src.quality.engine import run_checks


def run_raw_checks(ctx, spark):
    return run_checks(ctx, spark, layer="raw")
