"""F05: migração estrita, snapshots publicados, falha/retry, rollback e retenção."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from src.pipelines.download_home_credit import sha256
from src.publication.evolution import load_managed_contract, prepare_silver, validate_sources
from src.publication.protocol import (InjectedFailure, activate_publication, atomic_json, current_id,
    fail_at, load_publication_policy, open_publication, publish_snapshot)
from src.publication.retention import audit_retention, retention_fixture
from src.publication.source import open_f04_snapshots
from src.quality.contracts import load_contract, source_fingerprints
from src.quality.reconcile_bronze import compare_rows
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

CODE = ('src/pipelines/run_publication_demo.py', 'src/publication/protocol.py',
        'src/publication/evolution.py', 'src/publication/retention.py', 'src/publication/source.py',
        'src/quality/silver_contracts.py', 'src/quality/contracts.py', 'src/quality/reconcile_bronze.py',
        'src/silver/incremental.py', 'src/silver/initial_delta.py', 'src/silver/acceptance.py',
        'src/bronze/build_bronze.py', 'src/bronze/inputs.py', 'src/utils/spark.py',
        'src/utils/paths.py', 'src/utils/run_context.py')
CONFIG = ('configs/publication_policy_v1.yaml', 'configs/contracts/silver_managed_v2.yaml',
          'configs/contracts/silver_initial_v1.yaml', 'configs/contracts/home_credit_v1.yaml',
          'configs/silver_policy_v1.yaml', 'configs/spark.yaml', 'configs/paths.yaml',
          'requirements.lock', 'notebooks/analise_silver.ipynb')


def publish_silver(ctx, spark, registry, snapshot, plan, fingerprints, raw, *, hook=None):
    validate_sources(snapshot['frames'], plan)
    identity = {'scope': 'silver_v2', 'selection_id': snapshot['selection_id'],
        'input': snapshot['input'], 'configuration_and_code': fingerprints, 'raw': raw,
        'spark_version': spark.version}

    def build(tx):
        prepare_silver(tx, snapshot['frames'], plan, snapshot['counts'])

    return publish_snapshot(ctx, registry, spark, identity, fingerprints, build, hook=hook)


def run_publication_demo(ctx, spark, selection_id: str, f04_report: str):
    started = time.perf_counter()
    output = ctx.repo_root / 'artifacts/f05/runs' / (ctx.run_id + '.json')
    report = {'run_id': ctx.run_id, 'status': 'running', 'selection_id': selection_id, 'stage': 'configuration'}
    try:
        fingerprints = {n: sha256(ctx.repo_root / n) for n in CODE + CONFIG}
        load_publication_policy(ctx.repo_root / CONFIG[0])
        load_managed_contract(ctx.repo_root / CONFIG[1], ctx.repo_root / CONFIG[2])
        raw = source_fingerprints(ctx.raw_dir, load_contract(ctx.repo_root / CONFIG[3]))
        registry = ctx.repo_root / 'artifacts/publications' / selection_id / 'silver'
        report.update(registry=registry.relative_to(ctx.repo_root).as_posix(), fingerprints=fingerprints, raw=raw)
        report['publications'] = {}
        with open_f04_snapshots(ctx, spark, selection_id, f04_report) as (snapshots, plan):
            for snapshot in snapshots.values():
                snapshot['selection_id'] = selection_id
            report['stage'] = 'baseline_publication'
            baseline, baseline_run = publish_silver(RunContext.create(ctx.repo_root), spark, registry,
                snapshots['baseline'], plan, fingerprints, raw)
            report['publications']['baseline'] = baseline['publication_id']
            report['stage'] = 'strict_schema_negative_cases'
            from pyspark.sql import functions as F
            cases = snapshots['corrected']['frames']['credit_cases']
            bad_frames = [cases.drop('case_id'), cases.withColumn('target', F.col('target').cast('string')),
                          cases.withColumn('unexpected_column', F.lit(1))]
            rejected = 0
            for frame in bad_frames:
                try:
                    validate_sources({**snapshots['corrected']['frames'], 'credit_cases': frame}, plan)
                except ValueError:
                    rejected += 1
            if rejected != 3:
                raise AssertionError('Schema incompatível deveria bloquear')
            report['schema_rejections'] = rejected
            report['stage'] = 'failure_after_commit'
            # Mesmo intento, falha depois de um commit e antes do registro/aceite.
            # Se já existe manifesto aprovado, a prova não deve criar mutação nele.
            from src.quality.event_contracts import digest
            probe_identity = {'scope': 'silver_v2', 'selection_id': selection_id,
                'input': snapshots['corrected']['input'], 'configuration_and_code': fingerprints,
                'raw': raw, 'spark_version': spark.version}
            exists = (registry / 'manifests' / (digest(probe_identity)[:24] + '.json')).exists()
            before = current_id(registry)
            if not exists:
                try:
                    publish_silver(RunContext.create(ctx.repo_root), spark, registry, snapshots['corrected'],
                        plan, fingerprints, raw, hook=fail_at('after_commit:silver.credit_static:create'))
                except InjectedFailure:
                    if current_id(registry) != before:
                        raise AssertionError('Falha avançou CURRENT')
                    report['injected_failure_preserved_current'] = True
                else:
                    raise AssertionError('Falha simulada não ocorreu')
            else:
                report['injected_failure_preserved_current'] = 'already_published_verified_retry'
            corrected, correction_run = publish_silver(RunContext.create(ctx.repo_root), spark, registry,
                snapshots['corrected'], plan, fingerprints, raw)
            report['publications']['corrected'] = corrected['publication_id']
            report['stage'] = 'late_snapshot_publication'
            late, late_run = publish_silver(RunContext.create(ctx.repo_root), spark, registry,
                snapshots['late'], plan, fingerprints, raw)
            report['publications']['late'] = late['publication_id']
            report['attempts'] = [baseline_run, correction_run, late_run]
            report['stage'] = 'rollback_and_version_read'
            activate_publication(ctx.repo_root, registry, spark, baseline['publication_id'], ctx.run_id)
            with open_publication(ctx.repo_root, registry, spark) as (manifest, frames):
                if manifest['publication_id'] != baseline['publication_id']:
                    raise AssertionError('Rollback não selecionou baseline')
                report['rollback_proofs'] = {n: compare_rows(snapshots['baseline']['frames'][n],
                    frames['silver.' + n].select(*snapshots['baseline']['frames'][n].columns),
                    snapshots['baseline']['frames'][n].columns) for n in plan['tables']}
                if not all(p['success'] for p in report['rollback_proofs'].values()):
                    raise AssertionError('Leitura histórica diverge do baseline')
            activate_publication(ctx.repo_root, registry, spark, late['publication_id'], ctx.run_id)
            report['current_publication'] = current_id(registry)
            report['stage'] = 'retention'
            report['retention_audit'] = audit_retention(ctx.repo_root, registry, spark)
            report['retention_fixture'] = retention_fixture(spark)
        if any(sha256(ctx.repo_root / n) != h for n, h in fingerprints.items()):
            raise RuntimeError('Implementação mudou durante F05')
        report.update(status='passed', stage='complete', duration_seconds=round(time.perf_counter() - started, 3))
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error),
                      duration_seconds=round(time.perf_counter() - started, 3))
        atomic_json(output, report)
        raise
    atomic_json(output, report)
    return {'status': 'passed', 'run_id': ctx.run_id, 'report': str(output),
            'registry': str(registry), 'publications': report['publications'], 'duration_seconds': report['duration_seconds']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--f04-report', required=True, help='Relatório aprovado explícito, relativo ao repositório')
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    spark = create_spark_session(ctx.repo_root, app_name='f05-publication-demo', delta=True)
    spark.conf.set('spark.databricks.delta.snapshotPartitions', spark.conf.get('spark.sql.shuffle.partitions'))
    try:
        result = run_publication_demo(ctx, spark, args.sample, args.f04_report)
    finally:
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
