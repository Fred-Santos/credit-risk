"""F04 completo: eventos reais simulados, merge, reenvios e reconstrução."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import reduce
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

import yaml

from src.bronze.build_bronze import _ingestion_lock
from src.bronze.event_parquet import encode_events, publish_packet, read_packets, revision_index
from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.pipelines.run_bronze_mvp import _write_json
from src.quality.event_contracts import EventConflictError, digest, load_event_contract
from src.quality.reconcile_bronze import compare_rows
from src.quality.silver_contracts import load_silver_contract
from src.silver.incremental import (apply_packet, diagnostics, read_state, reconcile_state,
                                    validate_state, verify_state)
from src.silver.initial_delta import TABLES
from src.silver.read_bronze import open_bronze_snapshot
from src.silver.transforms import load_silver_policy
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

CODE = ('src/pipelines/run_incremental_demo.py', 'src/bronze/event_parquet.py',
        'src/silver/incremental.py', 'src/quality/event_contracts.py',
        'src/silver/read_bronze.py', 'src/silver/transforms.py', 'src/quality/silver_contracts.py',
        'src/quality/contracts.py', 'src/quality/reconcile_bronze.py', 'src/bronze/inputs.py',
        'src/bronze/build_bronze.py', 'src/pipelines/build_sample.py',
        'src/pipelines/run_bronze_mvp.py', 'src/pipelines/download_home_credit.py',
        'src/silver/initial_delta.py', 'src/quality/bronze_contract.py',
        'src/utils/spark.py', 'src/utils/paths.py', 'src/utils/run_context.py')
CONFIG = ('configs/incremental_policy_v1.yaml', 'configs/contracts/home_credit_events_v1.yaml',
          'configs/contracts/home_credit_v1.yaml', 'configs/contracts/silver_initial_v1.yaml',
          'configs/silver_policy_v1.yaml', 'configs/sample_policy.yaml', 'configs/paths.yaml',
          'configs/spark.yaml', 'requirements.lock', 'notebooks/analise_silver.ipynb')


def load_incremental_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text())
    expected = {
        'version': 1, 'scope': 'f04_local_simulated_incremental',
        'transport': 'typed_parquet_with_event_v1_and_bronze_metadata',
        'precedence': 'greatest_source_revision',
        'same_revision_conflict': 'reject_entire_batch_including_old_revisions',
        'duplicate_tie_break': 'smallest_delivery_id_after_payload_and_provenance_agreement',
        'absence': 'preserve_existing_rows_no_delete',
        'state': 'business_and_bronze_metadata_plus_event_identity',
        'reconstruction': 'group_max_revision_join_and_distinct_state',
        'late_case': 'second_eligible_case_in_first_temporal_batch',
        'correction_case': 'first_eligible_case_in_first_temporal_batch',
        'corrections': {'train_static_0': {'column': 'annuity_780A', 'add': 1.0},
                        'train_applprev_1': {'column': 'credamount_590A', 'add': 1.0}}}
    if (policy != expected or type(policy.get('version')) is not int
            or any(type(rule['add']) not in (int, float) for rule in policy['corrections'].values())):
        raise ValueError('Política incremental não suportada')
    return policy


def with_ordinals(frame, keys: list[str]):
    from pyspark.sql.types import StructType, StructField, LongType
    # Sort distribuído apenas das chaves. zipWithIndex traz ao driver somente
    # contagens por partição, sem janela global nem collect dos payloads.
    ordered = frame.select(*keys).orderBy(*keys)
    schema = StructType(ordered.schema.fields + [StructField('_ordinal', LongType(), False)])
    positions = frame.sparkSession.createDataFrame(
        ordered.rdd.zipWithIndex().map(lambda item: tuple(item[0]) + (item[1],)), schema)
    return frame.join(positions, keys, 'inner').select(*frame.columns, '_ordinal')


def generate_demo(root: Path, spark, *, bronze: dict, assignments, contract: dict,
                  snapshot: dict, binding: dict, policy: dict, batch_specs: list,
                  run_id: str) -> dict:
    from pyspark.sql import functions as F
    first_id = batch_specs[0]['id']
    first_keys = assignments.filter(F.col('_batch_id') == first_id).select('case_id')
    eligible = first_keys
    for table, rule in policy['corrections'].items():
        c = F.col(rule['column'])
        candidates = bronze[table].filter(c.isNotNull() & ~F.isnan(c) & ((c + rule['add']) != c))
        eligible = eligible.join(candidates.select('case_id').distinct(), 'case_id', 'left_semi')
    chosen = [r.case_id for r in eligible.orderBy('case_id').limit(2).collect()]
    if len(chosen) != 2:
        raise ValueError('Demonstração exige dois casos elegíveis no primeiro lote')
    correction_case, late_case = chosen
    correction_sources = {}
    for table, rule in policy['corrections'].items():
        c = F.col(rule['column'])
        source = bronze[table].filter((F.col('case_id') == correction_case) & c.isNotNull()
                                     & ~F.isnan(c) & ((c + rule['add']) != c))
        key = snapshot['tables'][table]['key']
        selected = source.orderBy(*key).select(*key).limit(1)
        correction_sources[table] = source.join(selected, key, 'left_semi')

    def packet(batch_id, sources, *, revision=1, scenario='baseline_replay', changed=False, duplicates=False):
        frames = {}
        for table in snapshot['tables']:
            source = sources.get(table, bronze[table].limit(0))
            ordered = with_ordinals(source, snapshot['tables'][table]['key'])
            if duplicates:
                even = ordered.withColumn('_ordinal', F.col('_ordinal') * 2)
                ordered = even.unionByName(even.withColumn('_ordinal', F.col('_ordinal') + 1))
            frames[table] = encode_events(ordered, contract, snapshot, selection_id=binding['selection_id'],
                stream_id=root.name, batch_id=batch_id, table=table, revision=revision, scenario=scenario,
                origin='home_credit_with_simulated_change' if changed else 'home_credit_snapshot')
        return publish_packet(root, spark, frames=frames, contract=contract, snapshot=snapshot,
                              binding=binding, batch_id=batch_id, run_id=run_id)

    publications = []
    for batch in batch_specs:
        keys = assignments.filter((F.col('_batch_id') == batch['id']) & (F.col('case_id') != late_case)).select('case_id')
        sources = {table: frame.join(keys, 'case_id', 'left_semi') for table, frame in bronze.items()}
        publications.append(packet(batch['id'], sources))
    corrected = {table: source.withColumn(policy['corrections'][table]['column'],
        F.col(policy['corrections'][table]['column']) + policy['corrections'][table]['add'])
        for table, source in correction_sources.items()}
    publications.append(packet('correction_r2', corrected, revision=2, scenario='correction_simulation', changed=True))
    publications.append(packet('duplicate_r2', corrected, revision=2, scenario='duplicate_delivery', changed=True, duplicates=True))
    publications.append(packet('old_revision_r1', correction_sources, scenario='late_arrival'))
    late = {table: frame.filter(F.col('case_id') == late_case) for table, frame in bronze.items()}
    publications.append(packet('late_case_r1', late, scenario='late_arrival'))
    conflicting = {table: source.withColumn(policy['corrections'][table]['column'],
        F.col(policy['corrections'][table]['column']) + 2 * policy['corrections'][table]['add'])
        for table, source in correction_sources.items()}
    try:
        packet('reject_old_conflict', conflicting, scenario='late_arrival', changed=True)
    except EventConflictError:
        conflict_rejected = not (root / 'reject_old_conflict').exists()
    else:
        raise AssertionError('Revisão antiga conflitante deveria rejeitar o lote')
    packets = read_packets(root, spark, snapshot, binding)
    baseline_ids = {b['id'] for b in batch_specs} | {'late_case_r1'}
    if {m['batch_id'] for m, _ in packets} != baseline_ids | {'correction_r2', 'duplicate_r2', 'old_revision_r1'}:
        raise ValueError('Stream da demonstração contém lote inesperado')
    baseline_proof = {}
    for table, source in bronze.items():
        pieces = [frames[table].select(*source.columns) for m, frames in packets if m['batch_id'] in baseline_ids]
        replay = reduce(lambda a, b: a.unionByName(b), pieces)
        baseline_proof[table] = compare_rows(source, replay, source.columns)
    if not all(p['success'] for p in baseline_proof.values()) or not conflict_rejected:
        raise ValueError('Gerador não preservou integralmente a Bronze/recorte')
    return {'publications': publications, 'baseline_reconciliation': baseline_proof,
            'old_revision_conflict_rejected': conflict_rejected, 'late_case': late_case,
            'correction_case': correction_case, 'changes': policy['corrections'],
            'bounded_driver_selection': 'two_case_ids_only_no_collect_of_payloads'}


def _history(packets, snapshot):
    return {table: reduce(lambda a, b: a.unionByName(b), [frames[table] for _, frames in packets])
            for table in snapshot['tables']}


def _equal_snapshots(before: dict, after: dict) -> dict:
    proofs = {n: compare_rows(before[n], after[n], before[n].columns) for n in before}
    if not all(p['success'] for p in proofs.values()):
        raise ValueError('Reenvio/revisão antiga alterou o estado')
    return proofs


def run_incremental_demo(ctx: RunContext, spark, selection_id: str) -> dict:
    started = time.perf_counter()
    output = ctx.repo_root / 'artifacts/f04/runs' / f'{ctx.run_id}.json'
    report = {'run_id': ctx.run_id, 'selection_id': selection_id, 'status': 'running',
              'scope': 'f04_incremental_demonstration_no_gold_publication', 'stage': 'configuration',
              'started_at_utc': ctx.started_at_utc}
    try:
        tracked = {name: sha256(ctx.repo_root / name) for name in CODE + CONFIG}
        report['artifact_sha256'] = tracked
        contract, snapshot = load_event_contract(ctx.repo_root / CONFIG[1], ctx.repo_root / CONFIG[2])
        policy = load_incremental_policy(ctx.repo_root / CONFIG[0])
        silver_policy, _ = load_silver_policy(ctx.repo_root / 'configs/silver_policy_v1.yaml',
            ctx.repo_root / CONFIG[2], ctx.repo_root / 'notebooks/analise_silver.ipynb')
        plan = load_silver_contract(ctx.repo_root / 'configs/contracts/silver_initial_v1.yaml',
            ctx.repo_root / CONFIG[2], ctx.repo_root / 'configs/silver_policy_v1.yaml',
            ctx.repo_root / 'notebooks/analise_silver.ipynb')
        bound = bind_sample(ctx, selection_id)
        selection = json.loads((bound.ctx.ingestion_dir / '_selection.json').read_text())
        if selection['identity']['policy_sha256'] != tracked['configs/sample_policy.yaml']:
            raise ValueError('Política dos lotes difere da seleção aprovada')
        events_parent = ctx.events_dir / selection_id
        events_parent.mkdir(parents=True, exist_ok=True)
        with _ingestion_lock(events_parent, '.f04_pipeline.lock'):
            report['stage'] = 'generation'
            with open_bronze_snapshot(bound, spark) as loaded:
                report['input'] = loaded.receipt
                binding = {**bound.descriptor, 'artifacts': tracked, 'spark_version': spark.version,
                           'delta_spark_version': version('delta-spark'),
                           'bronze_gate_sha256': loaded.receipt['gate_sha256'],
                           'bronze_run_id': loaded.receipt['bronze_run_id']}
                stream = 'f04_' + digest(binding)[:24]
                events_root = events_parent / stream
                state_root = ctx.silver_dir / 'samples' / selection_id / 'incremental' / stream
                identity = {'binding': binding, 'stream_id': stream, 'silver_contract_sha256': plan['contract_sha256']}
                report.update(stream_id=stream, events_root=str(events_root.relative_to(ctx.repo_root)),
                              state_root=str(state_root.relative_to(ctx.repo_root)), identity=identity)
                assignments = spark.read.parquet(str(bound.ctx.ingestion_dir / 'case_batches'))
                report['generation'] = generate_demo(events_root, spark, bronze=loaded.frames, assignments=assignments,
                    contract=contract, snapshot=snapshot, binding=binding, policy=policy,
                    batch_specs=selection['policy']['batches'], run_id=ctx.run_id)
            # Mantém a landing imutável durante todos os merges e a reconstrução.
            with _ingestion_lock(events_root, '.parquet_stream.lock'):
                packets = read_packets(events_root, spark, snapshot, binding)
                all_history = _history(packets, snapshot)
                indices = [revision_index(f) for f in all_history.values()]
                report['stage'] = 'incremental_merge'
                report['batches'] = []
                no_change_proofs = {}
                for manifest, frames in packets:
                    before = None
                    no_effect = manifest['batch_id'] in {'duplicate_r2', 'old_revision_r1'}
                    if no_effect:
                        versions = verify_state(state_root, spark, plan, identity)
                        before = read_state(state_root, spark, plan, version_map=versions)
                        indicators = diagnostics(before)
                    result = apply_packet(state_root, spark, manifest=manifest, frames=frames,
                        history_indices=indices, snapshot=snapshot, policy=silver_policy, plan=plan,
                        identity=identity, run_id=ctx.run_id)
                    report['batches'].append(result)
                    if before is not None:
                        after = read_state(state_root, spark, plan)
                        no_change_proofs[manifest['batch_id']] = _equal_snapshots(before, after)
                        if indicators != diagnostics(after) or result['versions_before'] != result['versions_after']:
                            raise AssertionError('Reenvio alterou diagnósticos/versões')
                report['stage'] = 'same_batch_retry'
                versions = verify_state(state_root, spark, plan, identity)
                before = read_state(state_root, spark, plan, version_map=versions)
                indicators = diagnostics(before)
                manifest, frames = packets[0]
                report['same_batch_retry'] = apply_packet(state_root, spark, manifest=manifest, frames=frames,
                    history_indices=indices, snapshot=snapshot, policy=silver_policy, plan=plan,
                    identity=identity, run_id=ctx.run_id)
                no_change_proofs['same_batch_retry'] = _equal_snapshots(before, read_state(state_root, spark, plan))
                if versions != verify_state(state_root, spark, plan, identity) or indicators != diagnostics(read_state(state_root, spark, plan)):
                    raise AssertionError('Retry alterou estado/diagnósticos/versões')
                report['idempotence'] = no_change_proofs
                report['stage'] = 'reconstruction'
                report['reconciliation'] = reconcile_state(state_root, spark, all_history, snapshot, silver_policy, plan)
                report['final_validation'] = validate_state(state_root, spark, plan,
                    {target: bound.expected_counts[source] for source, target in TABLES.items()})
                report['diagnostics_not_gold'] = diagnostics(read_state(state_root, spark, plan))
                report['final_versions'] = verify_state(state_root, spark, plan, identity)
                report['all_arrivals_simulated'] = True
                for name, expected in tracked.items():
                    if sha256(ctx.repo_root / name) != expected:
                        raise RuntimeError('Código/configuração mudou durante F04')
        report.update(status='passed', stage='complete', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      duration_seconds=round(time.perf_counter() - started, 3))
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error),
                      duration_seconds=round(time.perf_counter() - started, 3))
        _write_json(output, report)
        raise
    _write_json(output, report)
    return {'status': 'passed', 'run_id': ctx.run_id, 'stream_id': stream,
            'report': str(output), 'state_root': str(state_root), 'duration_seconds': report['duration_seconds']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    spark = create_spark_session(ctx.repo_root, app_name='f04-incremental-demo', delta=True)
    spark.conf.set('spark.databricks.delta.snapshotPartitions', spark.conf.get('spark.sql.shuffle.partitions'))
    try:
        result = run_incremental_demo(ctx, spark, args.sample)
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
