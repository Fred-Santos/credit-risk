"""Migração Silver v1 → v2 estrita, em tabelas privadas com commits retomáveis."""
from pathlib import Path

import yaml

from src.pipelines.download_home_credit import sha256
from src.quality.contracts import check_schema
from src.quality.reconcile_bronze import compare_rows
from src.quality.silver_contracts import validate_silver_frames
from src.silver.incremental import EVENT_STATE

MARKER = '_silver_contract_version'


def load_managed_contract(path: Path, parent: Path) -> dict:
    spec = yaml.safe_load(path.read_text())
    expected = {'version': 2, 'scope': 'managed_silver_publication',
        'parent_contract_sha256': sha256(parent),
        'schema_derivation': 'silver_initial_plus_f04_event_state_and_authorized_marker',
        'added_columns': {MARKER: 'int'}, 'backfill': {MARKER: 2},
        'unexpected_columns': 'fail', 'incompatible_types': 'fail', 'missing_required_columns': 'fail'}
    if spec != expected or type(spec.get('version')) is not int or type(spec['backfill'][MARKER]) is not int:
        raise ValueError('Contrato de migração Silver v2 não suportado')
    return spec


def v1_schema(plan: dict, name: str):
    return {**plan['tables'][name]['schema'], **EVENT_STATE}


def v2_schema(plan: dict, name: str):
    return {**v1_schema(plan, name), MARKER: 'int'}


def validate_sources(frames: dict, plan: dict):
    if set(frames) != set(plan['tables']):
        raise ValueError('Conjunto de tabelas Silver inesperado')
    for name, frame in frames.items():
        check_schema(frame, {'schema': v1_schema(plan, name)})


def migrate_table(tx, name: str, source, plan: dict):
    from pyspark.sql import functions as F
    schema = v1_schema(plan, name)
    check_schema(source, {'schema': schema})
    path, key = tx.table_path('silver', name), 'silver.' + name
    table = tx.create_table('silver', name, source)
    original = tx.spark.read.format('delta').option('versionAsOf', 0).load(str(path))
    check_schema(original, {'schema': schema})
    if not compare_rows(source, original, list(schema))['success']:
        raise ValueError('Cópia privada difere da entrada Silver versionada')
    actual = dict(table.toDF().dtypes)
    if actual == schema:
        with tx.commit(key, 'add_column'):
            tx.spark.sql(f'ALTER TABLE delta.`{path}` ADD COLUMNS ({MARKER} INT)')
    elif actual != v2_schema(plan, name):
        raise ValueError('Evolução inesperada ou tipo incompatível na tabela privada')
    table = tx.verify_owned(path, key)  # Reabrir depois do ALTER; não reutilizar schema analisado antigo.
    frame = table.toDF()
    if frame.filter(F.col(MARKER).isNotNull() & (F.col(MARKER) != 2)).limit(1).count():
        raise ValueError('Marcador de contrato inválido')
    if frame.filter(F.col(MARKER).isNull()).limit(1).count():
        with tx.commit(key, 'backfill'):
            table.update(condition=F.col(MARKER).isNull(), set={MARKER: F.lit(2).cast('int')})
    current = tx.record_table('silver', name, v2_schema(plan, name), plan['tables'][name]['key'])
    proof = compare_rows(source, current.select(*schema), list(schema))
    if not proof['success']:
        raise ValueError('Migração alterou negócio ou metadados de origem')
    tx.details.setdefault('migration', {})[name] = {'from_contract': 1, 'to_contract': 2,
        'before_delta_version': 0, 'after_delta_version': tx.entries[key]['version'], 'preservation': proof}
    tx.hook('after_migration:' + name)
    return current


def prepare_silver(tx, sources: dict, plan: dict, expected_counts: dict):
    from pyspark.sql import functions as F
    validate_sources(sources, plan)
    frames = {n: migrate_table(tx, n, sources[n], plan) for n in plan['tables']}
    tx.hook('before_silver_quality')
    for frame in frames.values():
        if frame.filter(F.col(MARKER).isNull() | (F.col(MARKER) != 2)).limit(1).count():
            raise ValueError('Backfill Silver v2 incompleto')
    result = validate_silver_frames({n: f.select(*plan['tables'][n]['schema']) for n, f in frames.items()},
                                    plan, expected_counts)
    tx.validations['silver_contracts'] = result
    tx.validations['migration_preservation'] = {'status': 'passed', 'tables': tx.details['migration']}
    tx.hook('after_silver_quality')
    return frames
