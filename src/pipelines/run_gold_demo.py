"""F06: ABT incremental e indicadores SQL em publicações Silver+Gold coerentes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from src.bronze.build_bronze import _ingestion_lock
from src.gold.model import build_abt, build_monthly, load_gold_contract
from src.gold.publish import publish_analytics
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import (InjectedFailure, activate_publication, atomic_json, current_id,
    fail_at, local, open_publication, verify_manifest)
from src.publication.retention import audit_retention
from src.publication.source import load_parent_plan
from src.quality.reconcile_bronze import compare_rows
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

CODE = ('src/pipelines/run_gold_demo.py', 'src/gold/model.py', 'src/gold/quality.py', 'src/gold/publish.py',
        'src/publication/protocol.py', 'src/publication/evolution.py', 'src/publication/retention.py',
        'src/publication/source.py', 'src/quality/contracts.py', 'src/quality/reconcile_bronze.py',
        'src/quality/silver_contracts.py', 'src/silver/initial_delta.py', 'src/silver/incremental.py',
        'src/silver/acceptance.py', 'src/bronze/build_bronze.py', 'src/utils/spark.py',
        'src/utils/run_context.py', 'src/utils/paths.py')
CONFIG = ('configs/contracts/gold_v1.yaml', 'configs/contracts/silver_managed_v2.yaml',
          'configs/contracts/silver_initial_v1.yaml', 'configs/contracts/home_credit_v1.yaml',
          'configs/silver_policy_v1.yaml', 'configs/publication_policy_v1.yaml', 'configs/spark.yaml',
          'configs/paths.yaml', 'requirements.lock', 'notebooks/analise_silver.ipynb')


def _parent(manifest, frames, plan):
    return {'manifest': manifest, 'frames': frames, 'silver': {n: frames['silver.' + n] for n in plan['tables']}}


def run_gold_demo(ctx, spark, selection_id: str, f05_report_relative: str):
    started = time.perf_counter()
    output = ctx.repo_root / 'artifacts/f06/runs' / (ctx.run_id + '.json')
    report = {'run_id': ctx.run_id, 'selection_id': selection_id, 'status': 'running', 'stage': 'configuration'}
    try:
        fingerprints = {n: sha256(ctx.repo_root / n) for n in CODE + CONFIG}
        spec = load_gold_contract(ctx.repo_root / CONFIG[0], ctx.repo_root / CONFIG[1])
        source_report_path = local(ctx.repo_root, f05_report_relative)
        source_report = json.loads(source_report_path.read_text())
        if source_report.get('status') != 'passed' or source_report.get('selection_id') != selection_id:
            raise ValueError('F06 exige relatório F05 aprovado da mesma seleção')
        source_registry = local(ctx.repo_root, source_report['registry'])
        expected_registry = ctx.repo_root / 'artifacts/publications' / selection_id / 'silver'
        if source_registry != expected_registry.resolve():
            raise ValueError('Registry Silver fora do namespace esperado')
        registry = ctx.repo_root / 'artifacts/publications' / selection_id / 'analytics'
        plan = load_parent_plan(ctx.repo_root)
        report.update(registry=registry.relative_to(ctx.repo_root).as_posix(), fingerprints=fingerprints,
                      f05_report=f05_report_relative, f05_report_sha256=sha256(source_report_path), publications={}, snapshots={})
        with _ingestion_lock(source_registry, '.publication.lock'):
            source_manifests = {}
            for name in ('baseline', 'corrected', 'late'):
                source_manifests[name], _ = verify_manifest(ctx.repo_root, source_registry,
                    source_report['publications'][name], spark)
            parent = None
            for name in ('baseline', 'corrected', 'late'):
                report['stage'] = 'publish_' + name
                source = source_manifests[name]
                kwargs = {'source_manifest': source, 'source_registry': source_registry,
                          'plan': plan, 'spec': spec, 'fingerprints': fingerprints, 'parent': parent}
                if name == 'corrected':
                    # Falha após o merge ABT privado e antes de indicadores/manifesto.
                    # Em retries globais já publicados, não modificar o artefato aprovado.
                    from src.quality.event_contracts import digest
                    parent_path = registry / 'manifests' / (parent['manifest']['publication_id'] + '.json')
                    source_path = source_registry / 'manifests' / (source['publication_id'] + '.json')
                    identity = {'scope': 'analytics_v1', 'selection_id': selection_id,
                        'silver_publication': {'manifest': source_path.relative_to(ctx.repo_root).as_posix(), 'sha256': sha256(source_path)},
                        'parent_analytics': {'manifest': parent_path.relative_to(ctx.repo_root).as_posix(), 'sha256': sha256(parent_path)},
                        'gold_contract_sha256': spec['contract_sha256'], 'code_and_configuration': fingerprints,
                        'spark_version': spark.version}
                    exists = (registry / 'manifests' / (digest(identity)[:24] + '.json')).exists()
                    before = current_id(registry)
                    if not exists:
                        try:
                            publish_analytics(RunContext.create(ctx.repo_root), spark, registry, **kwargs,
                                              hook=fail_at('after_commit:gold.abt:merge'))
                        except InjectedFailure:
                            if current_id(registry) != before:
                                raise AssertionError('Falha Gold expôs publicação parcial')
                            report['failure_after_gold_commit_preserved_current'] = True
                        else:
                            raise AssertionError('Falha Gold simulada não ocorreu')
                    else:
                        report['failure_after_gold_commit_preserved_current'] = 'already_published_verified_retry'
                manifest, attempt = publish_analytics(RunContext.create(ctx.repo_root), spark, registry, **kwargs)
                report['publications'][name] = manifest['publication_id']
                report['snapshots'][name] = {'attempt': attempt, 'update': manifest['details']['gold_update'],
                    'tables': {n: {k:t[k] for k in ('rows', 'version', 'delta_table_id', 'path')} for n,t in manifest['tables'].items()},
                    'validations': manifest['validations'], 'source_silver_publication': source['publication_id']}
                checked, frames = verify_manifest(ctx.repo_root, registry, manifest['publication_id'], spark)
                parent = _parent(checked, frames, plan)
            report['stage'] = 'historical_reproduction_and_restore'
            baseline_id, late_id = (report['publications'][n] for n in ('baseline', 'late'))
            activate_publication(ctx.repo_root, registry, spark, baseline_id, ctx.run_id)
            with open_publication(ctx.repo_root, registry, spark) as (manifest, frames):
                from pyspark import StorageLevel
                _, original_silver = verify_manifest(ctx.repo_root, source_registry, source_manifests['baseline']['publication_id'], spark)
                historical_abt = build_abt({n:original_silver['silver.' + n] for n in plan['tables']}).persist(StorageLevel.MEMORY_AND_DISK)
                try:
                    expected_history = {'gold.abt': historical_abt, 'gold.monthly_metrics': build_monthly(historical_abt)}
                    report['historical_proofs'] = {n: compare_rows(expected_history[n], frames[n], frames[n].columns)
                        for n in ('gold.abt', 'gold.monthly_metrics')}
                finally:
                    historical_abt.unpersist()
                if manifest['publication_id'] != baseline_id or not all(p['success'] for p in report['historical_proofs'].values()):
                    raise AssertionError('Publicação histórica não foi reproduzida')
            activate_publication(ctx.repo_root, registry, spark, late_id, ctx.run_id)
            # Retry da última publicação não produz outra cópia nem outro merge.
            final_manifest, final_frames = verify_manifest(ctx.repo_root, registry, late_id, spark)
            before = {n: t['files'] for n,t in final_manifest['tables'].items()}
            prior_parent_id = report['publications']['corrected']
            pm, pf = verify_manifest(ctx.repo_root, registry, prior_parent_id, spark)
            retried, attempt = publish_analytics(RunContext.create(ctx.repo_root), spark, registry,
                source_manifest=source_manifests['late'], source_registry=source_registry, plan=plan, spec=spec,
                fingerprints=fingerprints, parent=_parent(pm,pf,plan))
            if not attempt['reused'] or {n:t['files'] for n,t in retried['tables'].items()} != before:
                raise AssertionError('Retry de publicação Gold alterou os artefatos')
            report['retry'] = {'status': 'passed', 'publication_id': retried['publication_id'], 'reused': True}
            report['stage'] = 'retention_and_consumption'
            report['retention_audit'] = audit_retention(ctx.repo_root, registry, spark)
            with open_publication(ctx.repo_root, registry, spark) as (manifest, frames):
                if set(frames) != {'silver.' + n for n in plan['tables']} | {'gold.abt', 'gold.monthly_metrics'}:
                    raise ValueError('Publicação analítica incompleta')
                report['current_publication'] = manifest['publication_id']
                report['monthly_metrics'] = [r.asDict() for r in frames['gold.monthly_metrics'].orderBy('MONTH').collect()]
                report['abt_rows'] = frames['gold.abt'].count()
        if any(sha256(ctx.repo_root / n) != h for n,h in fingerprints.items()) or sha256(source_report_path) != report['f05_report_sha256']:
            raise RuntimeError('Código/configuração/entrada mudou durante F06')
        report.update(status='passed', stage='complete', duration_seconds=round(time.perf_counter() - started, 3))
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error), duration_seconds=round(time.perf_counter()-started,3))
        atomic_json(output, report)
        raise
    atomic_json(output, report)
    return {'status':'passed','run_id':ctx.run_id,'report':str(output),'registry':str(registry),
            'publications':report['publications'],'abt_rows':report['abt_rows'],'duration_seconds':report['duration_seconds']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',required=True)
    parser.add_argument('--f05-report',required=True)
    args=parser.parse_args()
    ctx=RunContext.create(Path(__file__).resolve().parents[2])
    spark=create_spark_session(ctx.repo_root,app_name='f06-gold-demo',delta=True)
    spark.conf.set('spark.databricks.delta.snapshotPartitions',spark.conf.get('spark.sql.shuffle.partitions'))
    try:
        result=run_gold_demo(ctx,spark,args.sample,args.f05_report)
    finally:
        spark.stop()
    print(json.dumps(result))


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f'ERRO: {error}',file=sys.stderr)
        raise SystemExit(1)
