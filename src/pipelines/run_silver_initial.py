"""Executa e aceita a Silver inicial, preservando pacotes e aceites anteriores."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys
import time

from src.bronze.build_bronze import _ingestion_lock
from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.pipelines.run_bronze_mvp import _write_json
from src.quality.silver_contracts import SilverContractError, load_silver_contract, validate_silver_frames
from src.silver.acceptance import publish_acceptance
from src.silver.initial_delta import TABLES, materialize_initial, open_initial_tables
from src.silver.read_bronze import open_bronze_snapshot
from src.silver.transforms import SilverTransformError, load_silver_policy, transform_snapshot
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

# Mesma composição de identidade de F03.4; alterações do writer geram outro pacote.
MATERIALIZATION_CODE = ('src/silver/initial_delta.py', 'src/silver/transforms.py',
                      'src/silver/read_bronze.py', 'src/pipelines/materialize_silver_initial.py')
EXECUTION_CODE = (*MATERIALIZATION_CODE, 'src/pipelines/run_silver_initial.py',
                  'src/silver/acceptance.py', 'src/quality/silver_contracts.py',
                  'src/bronze/inputs.py', 'src/quality/contracts.py',
                  'src/quality/reconcile_bronze.py', 'src/utils/spark.py',
                  'src/utils/paths.py', 'src/utils/run_context.py',
                  'src/bronze/build_bronze.py', 'src/quality/bronze_contract.py',
                  'src/pipelines/run_bronze_mvp.py', 'src/pipelines/build_sample.py',
                  'src/pipelines/download_home_credit.py')


def run_silver_initial(ctx: RunContext, spark, selection_id: str, *, existing: str = 'reuse') -> dict:
    """Ações Spark usam a sessão recebida; falhas sempre deixam relatório failed.

    existing=error recusa pacote já existente; reuse revalida tudo sem overwrite.
    O aceite é um recibo por execução, sem ponteiro latest ou publicação Gold.
    """
    started = time.perf_counter()
    output = ctx.repo_root / 'artifacts/silver_runs' / f'{ctx.run_id}.json'
    if output.exists():
        raise FileExistsError('run_id já utilizado; crie outro RunContext')
    report = {'run_id': ctx.run_id, 'started_at_utc': ctx.started_at_utc,
              'selection_id': selection_id, 'status': 'running', 'stage': 'configuration',
              'scope': 'silver_initial_operational_acceptance', 'existing': existing}
    try:
        if not re.fullmatch(r'[0-9a-f]{24}', selection_id):
            raise ValueError('selection_id deve ter 24 caracteres hexadecimais minúsculos')
        if existing not in {'reuse', 'error'}:
            raise ValueError('Comportamento para pacote existente inválido')
        paths = {'policy': ctx.repo_root / 'configs/silver_policy_v1.yaml',
                 'contract': ctx.repo_root / 'configs/contracts/home_credit_v1.yaml',
                 'notebook': ctx.repo_root / 'notebooks/analise_silver.ipynb',
                 'requirements': ctx.repo_root / 'requirements.lock',
                 'spark': ctx.repo_root / 'configs/spark.yaml'}
        fingerprints = {name: sha256(path) for name, path in paths.items()}
        tracked = {**{str(p.relative_to(ctx.repo_root)): fingerprints[name] for name, p in paths.items()},
                   **{name: sha256(ctx.repo_root / name) for name in EXECUTION_CODE},
                   'configs/contracts/silver_initial_v1.yaml': sha256(ctx.repo_root / 'configs/contracts/silver_initial_v1.yaml'),
                   'configs/paths.yaml': sha256(ctx.repo_root / 'configs/paths.yaml')}
        report['artifact_sha256'] = tracked
        policy, contract = load_silver_policy(paths['policy'], paths['contract'], paths['notebook'])
        plan = load_silver_contract(ctx.repo_root / 'configs/contracts/silver_initial_v1.yaml',
                                   paths['contract'], paths['policy'], paths['notebook'])
        report['compiled_contract'] = plan
        bound = bind_sample(ctx, selection_id)
        parent = ctx.silver_dir / 'samples' / selection_id
        if not parent.resolve().is_relative_to(ctx.silver_dir.resolve()):
            raise ValueError('Namespace fora da Silver configurada')
        parent.mkdir(parents=True, exist_ok=True)
        with _ingestion_lock(parent, '.silver_pipeline.lock'):
            report['stage'] = 'bronze_read'
            with open_bronze_snapshot(bound, spark) as loaded:
                report['input'] = loaded.receipt
                report['stage'] = 'transformation'
                transformed = transform_snapshot(loaded.frames, contract, policy)
                report['transformation_validation'] = transformed.report
                identity = {'selection_id': selection_id, 'bronze_gate_sha256': loaded.receipt['gate_sha256'],
                            'bronze_run_id': loaded.receipt['bronze_run_id'], 'configurations': fingerprints,
                            'code_sha256': {name: tracked[name] for name in MATERIALIZATION_CODE},
                            'table_mapping': TABLES, 'spark_version': spark.version,
                            'delta_spark_version': version('delta-spark')}
                report['stage'] = 'materialization'
                report['materialization_identity'] = identity
                result = materialize_initial(parent / 'initial', spark, identity=identity,
                    frames=transformed.frames, keys={n: s['key'] for n, s in contract['tables'].items()},
                    run_id=ctx.run_id, existing=existing)
                root = Path(result['root'])
                report['materialization'] = {**result, 'root': root.relative_to(ctx.repo_root).as_posix()}
                report['stage'] = 'persisted_contracts'
                with open_initial_tables(root, spark) as (frames, manifest):
                    if (manifest['identity'] != identity or any(manifest['tables'][n]['key'] != s['key']
                                                              for n, s in plan['tables'].items())):
                        raise ValueError('Pacote incompatível com identidade/contrato Silver')
                    report['validation'] = validate_silver_frames(frames, plan,
                        {target: bound.expected_counts[source] for source, target in TABLES.items()})
                    report['materialization_manifest_sha256'] = sha256(root / '_materialization.json')
            # Os dois leitores já revalidaram seus artefatos ao sair dos contextos.
            report['stage'] = 'acceptance'
            report.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          duration_seconds=round(time.perf_counter() - started, 3))
            receipt = publish_acceptance(ctx.repo_root, root, output, report)
            return {'status': 'passed', 'run_id': ctx.run_id, 'report': str(output),
                    'acceptance': str(receipt), 'materialization_id': root.name,
                    'reused': result['reused']}
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error),
                      finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      duration_seconds=round(time.perf_counter() - started, 3))
        if isinstance(error, SilverTransformError):
            report['transformation_validation'] = error.report
        if isinstance(error, SilverContractError):
            report['validation'] = error.report
        _write_json(output, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--existing', choices=['reuse', 'error'], default='reuse',
                        help='reuse revalida; error recusa pacote existente. Nunca sobrescreve.')
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    if not re.fullmatch(r'[0-9a-f]{24}', args.sample):
        # O core também valida o vínculo; este caminho gera diagnóstico sem iniciar JVM.
        run_silver_initial(ctx, None, args.sample, existing=args.existing)
    spark = None
    try:
        spark = create_spark_session(ctx.repo_root, app_name='silver-initial', delta=True)
        spark.conf.set('spark.databricks.delta.snapshotPartitions', spark.conf.get('spark.sql.shuffle.partitions'))
        result = run_silver_initial(ctx, spark, args.sample, existing=args.existing)
    except Exception as error:
        output = ctx.repo_root / 'artifacts/silver_runs' / f'{ctx.run_id}.json'
        if not output.exists():
            _write_json(output, {'run_id': ctx.run_id, 'selection_id': args.sample,
                                'status': 'failed', 'stage': 'spark_start',
                                'error_type': type(error).__name__, 'error': str(error)})
        raise
    finally:
        if spark is not None:
            spark.stop()
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f'ERRO: {error}', file=sys.stderr)
        raise SystemExit(1)
