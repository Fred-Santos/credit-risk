"""Demonstra o contrato com três linhas reais; somente a correção é artificial."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from src.bronze.event_batches import publish_batch
from src.bronze.inputs import bind_sample, verify_input
from src.pipelines.download_home_credit import sha256
from src.quality.event_contracts import (EventConflictError, load_event_contract,
                                         make_event, revision_action)
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    bound = bind_sample(ctx, args.sample)
    event_path = ctx.repo_root / 'configs/contracts/home_credit_events_v1.yaml'
    contract, snapshot = load_event_contract(event_path, ctx.repo_root / 'configs/contracts/home_credit_v1.yaml')
    binding = {**bound.descriptor, 'event_contract_sha256': sha256(event_path)}
    stream = 'contract_demo_v1'
    root = ctx.events_dir / args.sample / stream
    spark = create_spark_session(ctx.repo_root, app_name='credit-risk-event-contract')
    try:
        train = bound.ctx.ingestion_dir / 'parquet_files/train'
        frames = {name: spark.read.parquet(str(train / name)) for name in snapshot['tables']}
        batches = spark.read.parquet(str(bound.ctx.ingestion_dir / 'case_batches'))
        case = (batches.filter("_batch_id = 'b00_w000_051'")
                .join(frames['train_applprev_1'].select('case_id').distinct(), 'case_id')
                .orderBy('case_id').select('case_id').first()[0])
        payloads = {name: frame.filter(frame.case_id == case)
                    .orderBy(*snapshot['tables'][name]['key']).first().asDict()
                    for name, frame in frames.items()}
    finally:
        spark.stop()
    verify_input(bound)

    def event(table, batch, *, revision=1, ordinal=0, payload=None,
              scenario='baseline_replay', origin='home_credit_snapshot'):
        return make_event(contract, snapshot, selection_id=args.sample, stream_id=stream,
                          batch_id=batch, table=table, ordinal=ordinal, source_revision=revision,
                          payload=payload if payload is not None else payloads[table],
                          scenario=scenario, payload_origin=origin)

    initial = [event(name, 'demo_initial') for name in sorted(payloads)]
    corrected = dict(payloads['train_static_0'])
    column = 'annuity_780A'
    if corrected[column] is None or corrected[column] + 1.0 == corrected[column]:
        raise ValueError('Caso demonstrativo sem valor corrigível; revisar seleção da demonstração')
    corrected[column] += 1.0
    correction = event('train_static_0', 'demo_correction', revision=2, payload=corrected,
                       scenario='correction_simulation', origin='home_credit_with_simulated_change')
    late = event('train_static_0', 'demo_late', scenario='late_arrival')
    duplicates = [event('train_static_0', 'demo_duplicates', revision=2, ordinal=i,
                        payload=corrected, scenario='duplicate_delivery',
                        origin='home_credit_with_simulated_change') for i in range(2)]
    packets = [('demo_initial', initial), ('demo_correction', [correction]),
               ('demo_late', [late]), ('demo_duplicates', duplicates)]

    def publish(batch, events):
        return publish_batch(root, binding=binding, stream_id=stream, batch_id=batch,
                             events=events, contract=contract, snapshot=snapshot,
                             run_id=ctx.run_id, started_at_utc=ctx.started_at_utc)

    publications = [publish(batch, events) for batch, events in packets]
    retry = publish(*packets[0])
    bad = dict(corrected)
    bad[column] += 1.0
    conflict = event('train_static_0', 'demo_conflict', revision=2, payload=bad,
                     scenario='correction_simulation', origin='home_credit_with_simulated_change')
    try:
        publish('demo_conflict', [conflict])
    except EventConflictError:
        conflict_rejected = True
    else:
        raise AssertionError('Conflito de revisão deveria impedir publicação')
    actions, state = Counter(), {}
    for _, events in packets:
        for incoming in events:
            table = incoming['_table']
            action = revision_action(state.get(table), incoming, snapshot)
            actions[action] += 1
            if action in ('insert', 'update'):
                state[table] = incoming
    verify_input(bound)
    if sha256(event_path) != binding['event_contract_sha256']:
        raise RuntimeError('Contrato de eventos mudou durante execução')
    report = {
        'status': 'passed', 'run_id': ctx.run_id, 'binding': binding,
        'stream_id': stream, 'all_arrivals_simulated': True,
        'real_baseline_rows': 3, 'simulated_changed_field': f'train_static_0.{column}',
        'published_batches': [{'batch_id': p['batch_id'], 'event_count': p['event_count'],
                               'receipt_index': p['receipt_index'], 'reused': p['reused']}
                              for p in publications],
        'reference_actions': dict(actions), 'retry_reused': retry['reused'],
        'conflicting_revision_rejected': conflict_rejected,
        'conflict_batch_absent': not (root / 'demo_conflict').exists(),
        'scope': 'contract_reference_only_no_silver_merge',
        'code_sha256': {name: sha256(ctx.repo_root / name) for name in (
            'src/quality/event_contracts.py', 'src/bronze/event_batches.py',
            'src/pipelines/check_event_contract.py')},
    }
    if dict(actions) != {'insert': 3, 'update': 1, 'ignore_older_revision': 1, 'ignore_same_revision': 2}:
        raise AssertionError('Precedência de referência divergente')
    path = ctx.repo_root / 'artifacts/event_contract' / f'{ctx.run_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(path), 'actions': dict(actions)}))


if __name__ == '__main__':
    main()
