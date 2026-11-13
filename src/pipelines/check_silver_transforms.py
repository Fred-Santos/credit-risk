"""Executa tratamentos e verifica preservação, sem materializar Silver/Delta."""
import argparse
import json
from pathlib import Path

from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.silver.read_bronze import open_bronze_snapshot
from src.silver.transforms import SilverTransformError, load_silver_policy, transform_snapshot
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    output = ctx.repo_root / 'artifacts/silver_transforms' / f'{ctx.run_id}.json'
    paths = {'policy': ctx.repo_root / 'configs/silver_policy_v1.yaml',
             'contract': ctx.repo_root / 'configs/contracts/home_credit_v1.yaml',
             'notebook': ctx.repo_root / 'notebooks/analise_silver.ipynb'}
    report = {'run_id': ctx.run_id, 'selection_id': args.sample, 'status': 'running',
              'scope': 'validated_transformations_no_silver_materialization',
              'code_sha256': {name: sha256(ctx.repo_root / name) for name in (
                  'src/silver/transforms.py', 'src/silver/read_bronze.py',
                  'src/pipelines/check_silver_transforms.py')}}
    try:
        fingerprints = {name: sha256(path) for name, path in paths.items()}
        report['configuration_sha256'] = fingerprints
        policy, contract = load_silver_policy(paths['policy'], paths['contract'], paths['notebook'])
        bound = bind_sample(ctx, args.sample)
        spark = create_spark_session(ctx.repo_root, app_name='silver-transform-check')
        try:
            with open_bronze_snapshot(bound, spark) as loaded:
                report['input'] = loaded.receipt
                result = transform_snapshot(loaded.frames, contract, policy)
                report['validation'] = result.report
        finally:
            spark.stop()
        if fingerprints != {name: sha256(path) for name, path in paths.items()}:
            raise RuntimeError('Política/contrato/notebook mudou durante execução')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        if isinstance(error, SilverTransformError):
            report['validation'] = error.report
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(output)}))


if __name__ == '__main__':
    main()
