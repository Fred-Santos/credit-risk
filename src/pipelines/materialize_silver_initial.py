"""Cria o pacote técnico Silver inicial; aceite completo permanece posterior."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path

from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.silver.initial_delta import TABLES, materialize_initial, open_initial_tables
from src.silver.read_bronze import open_bronze_snapshot
from src.silver.transforms import SilverTransformError, load_silver_policy, transform_snapshot
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    config_paths = {'policy': ctx.repo_root / 'configs/silver_policy_v1.yaml',
                    'contract': ctx.repo_root / 'configs/contracts/home_credit_v1.yaml',
                    'notebook': ctx.repo_root / 'notebooks/analise_silver.ipynb',
                    'requirements': ctx.repo_root / 'requirements.lock',
                    'spark': ctx.repo_root / 'configs/spark.yaml'}
    report = {'run_id': ctx.run_id, 'selection_id': args.sample, 'status': 'running',
              'scope': 'initial_delta_materialization_pending_silver_acceptance',
              'code_sha256': {name: sha256(ctx.repo_root / name) for name in (
                  'src/silver/initial_delta.py', 'src/silver/transforms.py',
                  'src/silver/read_bronze.py', 'src/pipelines/materialize_silver_initial.py')}}
    output = ctx.repo_root / 'artifacts/silver_materialization' / f'{ctx.run_id}.json'
    try:
        fingerprints = {name: sha256(path) for name, path in config_paths.items()}
        report['configuration_sha256'] = fingerprints
        policy, contract = load_silver_policy(config_paths['policy'], config_paths['contract'], config_paths['notebook'])
        bound = bind_sample(ctx, args.sample)
        spark = create_spark_session(ctx.repo_root, app_name='silver-initial-delta', delta=True)
        # Derivado do paralelismo configurado para o laboratório; sem alterar configs congelados.
        spark.conf.set('spark.databricks.delta.snapshotPartitions', spark.conf.get('spark.sql.shuffle.partitions'))
        try:
            with open_bronze_snapshot(bound, spark) as loaded:
                report['input'] = loaded.receipt
                transformed = transform_snapshot(loaded.frames, contract, policy)
                report['transformation_validation'] = transformed.report
                identity = {'selection_id': args.sample, 'bronze_gate_sha256': loaded.receipt['gate_sha256'],
                            'bronze_run_id': loaded.receipt['bronze_run_id'], 'configurations': fingerprints,
                            'code_sha256': report['code_sha256'], 'table_mapping': TABLES,
                            'spark_version': spark.version, 'delta_spark_version': version('delta-spark')}
                result = materialize_initial(ctx.silver_dir / 'samples' / args.sample / 'initial', spark,
                    identity=identity, frames=transformed.frames,
                    keys={name: spec['key'] for name, spec in contract['tables'].items()}, run_id=ctx.run_id)
                report['materialization'] = result
                with open_initial_tables(Path(result['root']), spark) as (frames, manifest):
                    report['delta_consumed_rows'] = {name: frame.count() for name, frame in frames.items()}
                    report['materialization_manifest_sha256'] = sha256(Path(result['root']) / '_materialization.json')
        finally:
            spark.stop()
        if fingerprints != {name: sha256(path) for name, path in config_paths.items()}:
            raise RuntimeError('Configuração mudou durante materialização')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        if isinstance(error, SilverTransformError):
            report['transformation_validation'] = error.report
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(output)}))


if __name__ == '__main__':
    main()
