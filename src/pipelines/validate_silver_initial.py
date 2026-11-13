"""Valida contratos no pacote Delta explícito; não publica gate Silver."""
import argparse
import json
from pathlib import Path
import re

from src.bronze.inputs import bind_sample, verify_input
from src.pipelines.download_home_credit import sha256
from src.quality.silver_contracts import SilverContractError, load_silver_contract, validate_silver_frames
from src.silver.initial_delta import TABLES, open_initial_tables
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--materialization', required=True, help='ID explícito do pacote inicial, sem busca por latest')
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    output = ctx.repo_root / 'artifacts/silver_contract_validation' / f'{ctx.run_id}.json'
    paths = {'silver_contract': ctx.repo_root / 'configs/contracts/silver_initial_v1.yaml',
             'snapshot': ctx.repo_root / 'configs/contracts/home_credit_v1.yaml',
             'policy': ctx.repo_root / 'configs/silver_policy_v1.yaml',
             'notebook': ctx.repo_root / 'notebooks/analise_silver.ipynb'}
    report = {'run_id': ctx.run_id, 'selection_id': args.sample, 'materialization_id': args.materialization,
              'status': 'running', 'scope': 'silver_contract_validation_only_no_publication',
              'code_sha256': {name: sha256(ctx.repo_root / name) for name in (
                  'src/quality/silver_contracts.py', 'src/pipelines/validate_silver_initial.py',
                  'src/silver/initial_delta.py', 'src/silver/transforms.py')}}
    try:
        if not re.fullmatch(r'[0-9a-f]{24}', args.materialization):
            raise ValueError('ID de materialização inválido')
        fingerprints = {name: sha256(path) for name, path in paths.items()}
        report['configuration_sha256'] = fingerprints
        plan = load_silver_contract(paths['silver_contract'], paths['snapshot'], paths['policy'], paths['notebook'])
        report['compiled_contract'] = plan
        bound = bind_sample(ctx, args.sample)
        root = ctx.silver_dir / 'samples' / args.sample / 'initial' / args.materialization
        if not root.resolve().is_relative_to(ctx.silver_dir.resolve()):
            raise ValueError('Pacote fora do namespace Silver')
        spark = create_spark_session(ctx.repo_root, app_name='silver-contract-validation', delta=True)
        spark.conf.set('spark.databricks.delta.snapshotPartitions', spark.conf.get('spark.sql.shuffle.partitions'))
        try:
            with open_initial_tables(root, spark) as (frames, manifest):
                identity = manifest['identity']
                if (identity['selection_id'] != args.sample or identity['table_mapping'] != TABLES
                        or identity['configurations']['contract'] != plan['snapshot_contract_sha256']
                        or identity['configurations']['policy'] != plan['silver_policy_sha256']):
                    raise ValueError('Materialização incompatível com seleção/contrato/política')
                for name, spec in plan['tables'].items():
                    if manifest['tables'][name]['key'] != spec['key']:
                        raise ValueError('Chave registrada diverge do contrato Silver')
                report['input'] = {'root': root.relative_to(ctx.repo_root).as_posix(),
                                  'manifest_sha256': sha256(root / '_materialization.json'),
                                  'identity_sha256': manifest['identity_sha256'],
                                  'versions': {n: t['version'] for n, t in manifest['tables'].items()},
                                  'delta_table_ids': {n: t['delta_table_id'] for n, t in manifest['tables'].items()}}
                expected = {target: bound.expected_counts[source] for source, target in TABLES.items()}
                report['validation'] = validate_silver_frames(frames, plan, expected)
        finally:
            spark.stop()
        verify_input(bound)
        if fingerprints != {name: sha256(path) for name, path in paths.items()}:
            raise RuntimeError('Configuração mudou durante validação Silver')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        if isinstance(error, SilverContractError):
            report['validation'] = error.report
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(output)}))


if __name__ == '__main__':
    main()
