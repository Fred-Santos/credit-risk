"""Demonstra o carregamento lógico; não grava tabelas Silver."""
import argparse
import json
from pathlib import Path

from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.silver.read_bronze import open_bronze_snapshot
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    report = {'run_id': ctx.run_id, 'status': 'running', 'selection_id': args.sample,
              'code_sha256': {name: sha256(ctx.repo_root / name) for name in (
                  'src/silver/read_bronze.py', 'src/pipelines/check_silver_input.py')}}
    output = ctx.repo_root / 'artifacts/silver_input' / f'{ctx.run_id}.json'
    try:
        bound = bind_sample(ctx, args.sample)
        spark = create_spark_session(ctx.repo_root, app_name='silver-input-check')
        try:
            with open_bronze_snapshot(bound, spark) as loaded:
                receipt = loaded.receipt
                receipt['consumed_rows'] = {name: frame.count() for name, frame in loaded.frames.items()}
        finally:
            spark.stop()
        report.update(status='passed', input=receipt)
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'report': str(output)}))


if __name__ == '__main__':
    main()
