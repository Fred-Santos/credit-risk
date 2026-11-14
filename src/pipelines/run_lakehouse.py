"""F09: execução operacional sobre entradas locais aprovadas, sem baixar dados."""
import argparse
from functools import reduce
import json
from pathlib import Path

from src.pipelines.run_objects_demo import (CODE, CONFIG, _runtime, _packets_from_objects, _publish)
from src.bronze.build_bronze import _ingestion_lock
from src.bronze.inputs import bind_sample
from src.bronze.event_parquet import revision_index
from src.object_store.client import ObjectClient
from src.object_store.config import local_path
from src.object_store.incremental import ObjectIncremental
from src.object_store.mirror import mirror_inputs, verify_mirror
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.publication.protocol import atomic_json, local
from src.publication.source import open_f04_snapshots
from src.pipelines.download_home_credit import sha256
from src.silver.transforms import load_silver_policy
from src.silver.incremental import reconstruct
from src.quality.reconcile_bronze import compare_rows
from src.quality.event_contracts import digest
from src.gold.model import load_gold_contract
from src.utils.run_context import RunContext
from src.operation.metrics import StageClock, batch_counters, publication_inventory


def select_packets(packets, mode, batch):
    if mode not in ('update', 'replay', 'rebuild'):
        raise ValueError('Modo desconhecido')
    if mode == 'update' and not batch:
        raise ValueError('update exige --batch como limite inclusivo')
    ids = [m['batch_id'] for m, _ in packets]
    if batch is not None and batch not in ids:
        raise ValueError('Lote ausente no manifesto aprovado')
    return packets[:ids.index(batch)+1] if batch else packets


def execute(ctx, spark, *, sample, source_report, mode, batch=None, operation_id=None, on_stage=None):
    repo = ctx.repo_root
    output = repo/'artifacts/f09/runs'/(ctx.run_id+'.json')
    report = {'run_id': ctx.run_id, 'mode': mode, 'batch': batch,
              'selection_id': sample, 'status': 'running', 'stage': 'inputs'}
    timer=StageClock()
    def stage(name):
        timer.enter(name)
        report['stage'] = name
        atomic_json(output, report)
        if on_stage is not None: on_stage(name)
    try:
        stage('inputs')
        fingerprints = {p: sha256(repo/p) for p in (*CODE, *CONFIG, 'src/pipelines/run_lakehouse.py',
            'src/operation/runner.py', 'src/pipelines/operate_lakehouse.py', 'src/operation/metrics.py')}
        client = ObjectClient(repo)
        policy, snapshot = load_silver_policy(repo/'configs/silver_policy_v1.yaml',
            repo/'configs/contracts/home_credit_v1.yaml', repo/'notebooks/analise_silver.ipynb')
        spec = load_gold_contract(repo/'configs/contracts/gold_v1.yaml', repo/'configs/contracts/silver_managed_v2.yaml')
        source_path = local(repo, source_report)
        source = json.loads(source_path.read_text())
        bound = bind_sample(ctx, sample)
        with _ingestion_lock(local_path(repo, client.config['control_directory']), '.operation.lock'):
            with open_f04_snapshots(ctx, spark, sample, source_report) as (_, plan):
                stage('mirror_inputs')
                mirror, key = mirror_inputs(ctx, client, bound, source_path)
                metadata = sorted(source['generation']['publications'], key=lambda m:m['receipt_index'])
                selected = select_packets([(m,None) for m in metadata], mode, batch)
                selected_source = {**source,'generation':{**source['generation'],'publications':[m for m,_ in selected]}}
                packets = _packets_from_objects(client, mirror, selected_source, spark, snapshot)
                report['input_metrics']={'catalogue_batches_available':len(metadata),'catalogue_batches_read':len(packets),'selected_batches':len(packets),
                    'mirror_files':len(mirror['files']),'mirror_logical_bytes':sum(r['bytes'] for r in mirror['files'].values())}
                identity = {'scope': 'operational_incremental_v1', 'selection_id': sample,
                    'source_binding': source['identity']['binding'], 'source_stream_id': source['stream_id'],
                    'mirror': {'key': key, 'sha256': client.checksum(key)},
                    'fingerprints': fingerprints, 'runtime': _runtime(repo, spark)}
                # Reconstrução é isolada; update/replay compartilham estado idempotente.
                if mode == 'rebuild': identity['rebuild_run_id'] = operation_id or ctx.run_id
                prefix = client.config['prefix']+'/operations/'+sample+'/'+digest(identity)[:24]
                state = ObjectIncremental(client, spark, prefix, identity, plan)
                report.update(state_prefix=prefix, fingerprints=fingerprints, stage='incremental')
                stage('incremental')
                # Nunca regredir um estado que já consumiu além do limite solicitado.
                selected = {m['batch_id'] for m, _ in packets}
                applied = client.list(prefix+'/applied/')
                if any(k.rsplit('/', 1)[-1][:-5] not in selected for k in applied):
                    raise ValueError('Limite anterior ao estado atual; use rebuild para resultado histórico')
                histories = {name: reduce(lambda a,b:a.unionByName(b), [f[name] for _,f in packets]) for name in packets[0][1]}
                indices = [revision_index(f) for f in histories.values()]
                report['batches'] = []
                for m,f in packets:
                    report['batches'].append(state.apply(m,f,indices,snapshot,policy,ctx.run_id))
                    atomic_json(output,report)
                versions = state.verify()
                frames = state.read(versions)
                stage('reconciliation')
                expected = reconstruct(histories, snapshot, policy)
                proofs = {n: compare_rows(expected[n], frames[n], expected[n].columns) for n in frames}
                if not all(p['success'] for p in proofs.values()): raise ValueError('Reconstrução diverge do incremento')
                counts = {n:f.count() for n,f in frames.items()}
                # Fixar recibos imutáveis, nunca referenciar o estado mutável no manifesto.
                refs = [identity['mirror']]
                refs += [{'key': k, 'sha256': client.checksum(k)} for k in sorted(client.list(prefix+'/applied/'))]
                publication_identity = {'scope': 'operational_analytics_v1', 'selection_id': sample,
                    'state_identity': identity, 'source_versions': versions, 'references': refs}
                # Registry separado mantém CURRENT da demonstração F08 intacto.
                registry = client.config['prefix']+'/operational-publications/'+sample
                verify_mirror(client, mirror)
                stage('publication')
                manifest, attempt = _publish(ctx, client, registry, spark, frames, plan, counts, spec,
                    publication_identity, fingerprints, refs)
                verify_mirror(client, mirror)
                stage('metrics_collection')
                report['publication_metrics']=publication_inventory(client,manifest)
                report['row_metrics']=batch_counters(report['batches'])
                report.update(status='passed', stage='complete', publication_id=manifest['publication_id'],
                    registry=registry, source_versions=versions, reconstruction=proofs, counts=counts, attempt=attempt)
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        from src.quality.silver_contracts import SilverContractError
        from src.gold.quality import GoldQualityError
        if isinstance(error,(SilverContractError,GoldQualityError)):report['quality_failure']=error.report
        report['timing']=timer.snapshot()
        report['partial_row_metrics']=batch_counters(report.get('batches',[]))
        report['partial_row_metrics']['rejected_rows']=None
        atomic_json(output, report)
        raise
    report['timing']=timer.snapshot()
    atomic_json(output, report)
    return {'status':'passed', 'run_id':ctx.run_id, 'report':str(output), 'publication_id':report['publication_id']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--source-report', required=True, help='Relatório F04 aprovado')
    parser.add_argument('--mode', choices=('update','replay','rebuild'), required=True)
    parser.add_argument('--batch', help='Último lote incluído; obrigatório em update')
    args = parser.parse_args()
    if args.mode == 'update' and not args.batch: parser.error('update exige --batch')
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    service = ObjectService(ctx.repo_root); spark = None
    already_running = service.status()['status'] == 'running'
    try:
        service.start()
        spark = create_object_spark(ctx.repo_root, app_name='lakehouse-operation')
        result = execute(ctx, spark, sample=args.sample, source_report=args.source_report, mode=args.mode, batch=args.batch)
    finally:
        if spark is not None: spark.stop()
        if not already_running: service.stop()
    print(json.dumps(result))


if __name__ == '__main__': main()
