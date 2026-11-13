"""Precedência, deduplicação e merge Delta local; sem publicação Gold/F05."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import time

from src.bronze.build_bronze import _ingestion_lock
from src.bronze.event_parquet import check_conflicts, revision_index
from src.pipelines.run_bronze_mvp import _write_json
from src.quality.bronze_contract import METADATA
from src.quality.contracts import check_schema
from src.quality.event_contracts import EventConflictError, digest
from src.quality.reconcile_bronze import compare_rows
from src.quality.silver_contracts import validate_silver_frames
from src.silver.initial_delta import TABLES
from src.silver.transforms import transform_table, verify_transformation

EVENT_STATE = {'_source_system': 'string', '_selection_id': 'string', '_stream_id': 'string',
               '_source_revision': 'bigint', '_event_id': 'string', '_payload_sha256': 'string',
               '_is_simulated': 'boolean'}


def state_columns(snapshot: dict, table: str) -> list[str]:
    return list(snapshot['tables'][table]['schema']) + list(METADATA) + list(EVENT_STATE)


def deduplicate(frame, snapshot: dict, table: str):
    from pyspark.sql import Window, functions as F
    check_conflicts([revision_index(frame)])
    key = snapshot['tables'][table]['key']
    rows = frame.count()
    unique_revisions = frame.select(*key, '_source_revision').distinct().count()
    window = Window.partitionBy(*key).orderBy(F.desc('_source_revision'), F.asc('_delivery_id'))
    chosen = frame.withColumn('_chosen', F.row_number().over(window)).filter('_chosen = 1').drop('_chosen')
    candidates = chosen.count()
    return chosen, {'input_deliveries': rows, 'duplicate_deliveries': rows - unique_revisions,
                    'superseded_revisions': unique_revisions - candidates, 'candidate_keys': candidates}


def transform_candidates(frame, snapshot: dict, policy: dict, table: str):
    business_and_metadata = list(snapshot['tables'][table]['schema']) + list(METADATA)
    source = frame.select(*business_and_metadata)
    dates = policy['tables'][table]['cast_to_date']
    treated, metrics = transform_table(table, source, snapshot['tables'][table], dates)
    proof = verify_transformation(source, treated, snapshot['tables'][table], dates)
    if not proof['success']:
        raise ValueError('Candidato incremental diverge do tratamento aprovado')
    # Mesma projeção de datas, mantendo a identidade do evento e a proveniência.
    from pyspark.sql import functions as F
    result = frame.select(*[F.to_date(c, 'yyyy-MM-dd').alias(c) if c in dates else F.col(c)
                             for c in state_columns(snapshot, table)])
    return result, {**metrics, 'preservation': proof}


def _version(spark, path: Path) -> int:
    from delta.tables import DeltaTable
    return int(DeltaTable.forPath(spark, str(path)).history(1).select('version').first()[0])


def _commit_metadata(spark, value: dict):
    """Caller restaura a configuração da sessão depois da operação Delta."""
    name = 'spark.databricks.delta.commitInfo.userMetadata'
    prior = spark.conf.get(name, None)
    spark.conf.set(name, json.dumps(value, sort_keys=True))
    return name, prior


def _restore_conf(spark, name, prior):
    if prior is None:
        spark.conf.unset(name)
    else:
        spark.conf.set(name, prior)


def initialize_state(root: Path, spark, *, identity: dict, plan: dict, run_id: str):
    from delta.tables import DeltaTable
    from pyspark.sql.types import StructType, StructField, _parse_datatype_string
    if root.name != identity['stream_id']:
        raise ValueError('Estado fora do namespace do stream')
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        header = json.loads((root / '_state.json').read_text())
        if header['identity'] != identity or header['identity_sha256'] != digest(identity):
            raise ValueError('Estado incremental vinculado a outra identidade')
        verify_state(root, spark, plan, identity)
        return header
    stage = Path(tempfile.mkdtemp(prefix='.state_stage_', dir=root.parent))
    try:
        tables = {}
        for name, spec in plan['tables'].items():
            schema = StructType([StructField(c, _parse_datatype_string(t), True)
                                for c, t in {**spec['schema'], **EVENT_STATE}.items()])
            conf, prior = _commit_metadata(spark, {'scope': 'f04', 'identity': digest(identity), 'initialize': True})
            try:
                spark.createDataFrame([], schema).write.format('delta').mode('errorifexists').save(str(stage / name))
            finally:
                _restore_conf(spark, conf, prior)
            tables[name] = DeltaTable.forPath(spark, str(stage / name)).detail().select('id').first()[0]
        header = {'format_version': 1, 'scope': 'f04_working_state_no_gold_publication',
                  'identity': identity, 'identity_sha256': digest(identity), 'tables': tables,
                  'created_by_run_id': run_id}
        (stage / '_state.json').write_text(json.dumps(header, indent=2) + '\n')
        stage.rename(root)
        return header
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_state(root: Path, spark, plan: dict, identity: dict) -> dict:
    from delta.tables import DeltaTable
    header = json.loads((root / '_state.json').read_text())
    if (header.get('format_version') != 1 or header['identity'] != identity
            or header['identity_sha256'] != digest(identity) or set(header['tables']) != set(plan['tables'])):
        raise ValueError('Cabeçalho do estado incremental incompatível')
    observed = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')}
    if observed != set(plan['tables']) | ({'applied'} if (root / 'applied').exists() else set()):
        raise ValueError('Tabelas inesperadas no estado incremental')
    versions = {}
    for name, spec in plan['tables'].items():
        path = root / name
        delta = DeltaTable.forPath(spark, str(path))
        if delta.detail().select('id').first()[0] != header['tables'][name]:
            raise ValueError('UUID Delta inesperado no estado incremental')
        check_schema(delta.toDF(), {'schema': {**spec['schema'], **EVENT_STATE}})
        for record in delta.history().select('userMetadata').collect():
            metadata = json.loads(record[0] or '{}')
            if metadata.get('scope') != 'f04' or metadata.get('identity') != digest(identity):
                raise ValueError('Commit externo não reconhecido no estado incremental')
        versions[name] = _version(spark, path)
    return versions


def _metrics(target, source, keys: list[str]) -> dict:
    from pyspark.sql import functions as F
    existing = target.select(*keys, F.col('_source_revision').alias('_current_revision'),
                             F.col('_payload_sha256').alias('_current_payload'))
    joined = source.join(existing, keys, 'left')
    same = F.col('_source_revision') == F.col('_current_revision')
    if joined.filter(same & (F.col('_payload_sha256') != F.col('_current_payload'))).limit(1).count():
        raise EventConflictError('Conflito contra estado Silver atual')
    conditions = {'inserts': F.col('_current_revision').isNull(),
                  'updates': F.col('_source_revision') > F.col('_current_revision'),
                  'ignored_same_revision': same,
                  'ignored_older_revision': F.col('_source_revision') < F.col('_current_revision')}
    values = joined.agg(*[F.sum(c.cast('long')).alias(n) for n, c in conditions.items()]).first().asDict()
    return {n: int(v or 0) for n, v in values.items()}


def read_state(root: Path, spark, plan: dict, *, version_map: dict | None = None) -> dict:
    result = {}
    for name in plan['tables']:
        reader = spark.read.format('delta')
        if version_map is not None:
            reader = reader.option('versionAsOf', version_map[name])
        result[name] = reader.load(str(root / name))
    return result


def validate_state(root: Path, spark, plan: dict, expected_counts: dict | None = None):
    frames = read_state(root, spark, plan)
    return validate_silver_frames({n: f.select(*plan['tables'][n]['schema']) for n, f in frames.items()},
                                  plan, expected_counts)


def apply_packet(root: Path, spark, *, manifest: dict, frames: dict, history_indices: list,
                 snapshot: dict, policy: dict, plan: dict, identity: dict, run_id: str) -> dict:
    from delta.tables import DeltaTable
    from pyspark import StorageLevel
    started = time.perf_counter()
    if (manifest['binding'] != identity['binding'] or manifest['stream_id'] != identity['stream_id']
            or set(frames) != set(TABLES) or set(manifest['counts']) != set(TABLES)):
        raise ValueError('Pacote pertence a outro stream/estado')
    root.parent.mkdir(parents=True, exist_ok=True)
    with _ingestion_lock(root.parent, '.incremental_state.lock'):
        initialize_state(root, spark, identity=identity, plan=plan, run_id=run_id)
        before = verify_state(root, spark, plan, identity)
        check_conflicts(history_indices + [revision_index(f) for f in frames.values()])
        receipt = root / 'applied' / (manifest['batch_id'] + '.json')
        if receipt.exists():
            prior = json.loads(receipt.read_text())
            if prior['packet_sha256'] != manifest['packet_sha256'] or prior['identity_sha256'] != digest(identity):
                raise ValueError('Recibo aplicado incompatível com pacote/estado')
        prepared, metrics = {}, {}
        try:
            # Todas as tabelas são deduplicadas/tratadas antes de qualquer merge.
            for table in TABLES:
                chosen, dedup = deduplicate(frames[table], snapshot, table)
                treated, transformation = transform_candidates(chosen, snapshot, policy, table)
                treated = treated.persist(StorageLevel.MEMORY_AND_DISK)
                prepared[table] = treated
                name = TABLES[table]
                action = _metrics(DeltaTable.forPath(spark, str(root / name)).toDF(), treated,
                                  snapshot['tables'][table]['key'])
                metrics[name] = {**dedup, **action, 'transformation': transformation}
            for table, source in prepared.items():
                name = TABLES[table]
                stats = metrics[name]
                if stats['inserts'] + stats['updates'] == 0:
                    continue  # Evita até o commit vazio em reenvios e revisões antigas.
                keys = snapshot['tables'][table]['key']
                condition = ' AND '.join(f't.`{c}` = s.`{c}`' for c in keys)
                conf, prior = _commit_metadata(spark, {'scope': 'f04', 'identity': digest(identity),
                    'batch_id': manifest['batch_id'], 'packet_sha256': manifest['packet_sha256'], 'run_id': run_id})
                try:
                    (DeltaTable.forPath(spark, str(root / name)).alias('t')
                     .merge(source.alias('s'), condition)
                     .whenMatchedUpdateAll(condition='s._source_revision > t._source_revision')
                     .whenNotMatchedInsertAll().execute())
                finally:
                    _restore_conf(spark, conf, prior)
                operation = DeltaTable.forPath(spark, str(root / name)).history(1).first().asDict()
                actual = operation['operationMetrics']
                if (int(actual.get('numTargetRowsInserted', -1)) != stats['inserts']
                        or int(actual.get('numTargetRowsUpdated', -1)) != stats['updates']):
                    raise RuntimeError('Métricas do commit Delta divergem da classificação')
            validation = validate_state(root, spark, plan)
            after = verify_state(root, spark, plan, identity)
            report = {'status': 'passed', 'batch_id': manifest['batch_id'], 'packet_sha256': manifest['packet_sha256'],
                      'identity_sha256': digest(identity), 'run_id': run_id, 'metrics': metrics,
                      'versions_before': before, 'versions_after': after, 'validation': validation,
                      'reused_receipt': receipt.exists(), 'duration_seconds': round(time.perf_counter() - started, 3)}
            if not receipt.exists():
                _write_json(receipt, report)
            return report
        finally:
            for frame in prepared.values():
                frame.unpersist()


def reconstruct(frames_by_table: dict, snapshot: dict, policy: dict) -> dict:
    """Oráculo distribuído independente: group max + join, sem usar deduplicate/merge."""
    from pyspark.sql import functions as F
    check_conflicts([revision_index(f) for f in frames_by_table.values()])
    result = {}
    for table, events in frames_by_table.items():
        key = snapshot['tables'][table]['key']
        highest = events.groupBy(*key).agg(F.max('_source_revision').alias('_source_revision'))
        winners = events.join(highest, key + ['_source_revision'], 'inner')
        dates = policy['tables'][table]['cast_to_date']
        # Parse aprovado é conferido separadamente pela API de transformação.
        source_cols = list(snapshot['tables'][table]['schema']) + list(METADATA)
        transform_table(table, winners.select(*source_cols), snapshot['tables'][table], dates)
        result[TABLES[table]] = winners.select(*[
            F.to_date(c, 'yyyy-MM-dd').alias(c) if c in dates else F.col(c)
            for c in state_columns(snapshot, table)]).distinct()
    return result


def reconcile_state(root: Path, spark, history: dict, snapshot: dict, policy: dict, plan: dict) -> dict:
    expected = reconstruct(history, snapshot, policy)
    actual = read_state(root, spark, plan)
    proofs = {name: compare_rows(expected[name], actual[name], expected[name].columns) for name in expected}
    if not all(p['success'] for p in proofs.values()):
        raise ValueError(f'Incremental diverge da reconstrução: {proofs}')
    return {'status': 'passed', 'algorithm': 'group_max_revision_join_distinct_vs_delta_merge', 'tables': proofs}


def diagnostics(frames: dict) -> dict:
    """Diagnósticos F04; não cria indicadores Gold nem publicação analítica."""
    from pyspark.sql import functions as F
    base, static, history = (frames[n] for n in TABLES.values())
    months = base.groupBy('MONTH').agg(F.count('*').alias('cases'), F.sum('target').alias('target_1')).orderBy('MONTH')
    return {'months': [r.asDict() for r in months.collect()],
            'cases': base.count(), 'static_rows': static.count(), 'historical_rows': history.count(),
            'cases_with_history': history.select('case_id').distinct().count()}
