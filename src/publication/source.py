"""Entrada F05: snapshots explícitos do replay F04 aprovado, sob lock do produtor."""
from contextlib import contextmanager
import json
from pathlib import Path

from src.bronze.build_bronze import _ingestion_lock
from src.bronze.inputs import bind_sample
from src.bronze.event_parquet import parquet_checksums
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import local
from src.quality.silver_contracts import load_silver_contract
from src.silver.incremental import read_state, verify_state

SNAPSHOTS = {'baseline': 'b02_w078_091', 'corrected': 'correction_r2', 'late': 'late_case_r1'}


def load_parent_plan(repo: Path):
    return load_silver_contract(repo / 'configs/contracts/silver_initial_v1.yaml',
        repo / 'configs/contracts/home_credit_v1.yaml', repo / 'configs/silver_policy_v1.yaml',
        repo / 'notebooks/analise_silver.ipynb')


@contextmanager
def open_f04_snapshots(ctx, spark, selection_id: str, report_relative: str):
    bound = bind_sample(ctx, selection_id)
    path = local(ctx.repo_root, report_relative)
    report = json.loads(path.read_text())
    if (report.get('status') != 'passed' or report.get('selection_id') != selection_id
            or report.get('reconciliation', {}).get('status') != 'passed'
            or not report.get('all_arrivals_simulated')
            or report.get('final_validation', {}).get('status') != 'passed'
            or not report['reconciliation'].get('tables')
            or not all(p['success'] for p in report['reconciliation']['tables'].values())):
        raise ValueError('Entrada F04 não aprovada')
    expected = {target: bound.expected_counts[source] for source, target in
                {'train_base': 'credit_cases', 'train_static_0': 'credit_static', 'train_applprev_1': 'previous_applications'}.items()}
    if {n: t['rows'] for n, t in report['final_validation']['tables'].items()} != expected:
        raise ValueError('Contagens F04 não correspondem ao recorte')
    root = local(ctx.repo_root, report['state_root'])
    if root != (ctx.silver_dir / 'samples' / selection_id / 'incremental' / report['stream_id']).resolve():
        raise ValueError('F04 fora do namespace esperado')
    events = local(ctx.repo_root, report['events_root'])
    for packet in report['generation']['publications']:
        if parquet_checksums(events / packet['batch_id']) != packet['output_checksums']:
            raise ValueError('Landing de origem F04 foi alterada')
    plan = load_parent_plan(ctx.repo_root)
    original_hash = sha256(path)
    with _ingestion_lock(root.parent, '.incremental_state.lock'):
        if verify_state(root, spark, plan, report['identity']) != report['final_versions']:
            raise ValueError('Estado F04 avançou fora do relatório aprovado')
        snapshots = {}
        delta_ids = json.loads((root / '_state.json').read_text())['tables']
        for name, batch in SNAPSHOTS.items():
            record = next(r for r in report['batches'] if r['batch_id'] == batch)
            receipt = root / 'applied' / (batch + '.json')
            stored = json.loads(receipt.read_text())
            if stored['packet_sha256'] != record['packet_sha256'] or stored['versions_after'] != record['versions_after']:
                raise ValueError('Recibo F04 divergente')
            counts = {n: t['rows'] for n, t in record['validation']['tables'].items()}
            snapshots[name] = {'frames': read_state(root, spark, plan, version_map=record['versions_after']),
                'counts': counts, 'input': {'f04_report': report_relative, 'f04_report_sha256': original_hash,
                    'f04_identity': report['identity'], 'batch_id': batch, 'packet_sha256': record['packet_sha256'],
                    'source_delta_versions': record['versions_after'], 'source_delta_ids': delta_ids,
                    'source_receipt_sha256': sha256(receipt)}}
        yield snapshots, plan
        if sha256(path) != original_hash or verify_state(root, spark, plan, report['identity']) != report['final_versions']:
            raise RuntimeError('Entrada F04 mudou durante F05')
