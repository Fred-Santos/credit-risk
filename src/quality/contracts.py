"""Contratos de snapshots; revisões/eventos exigirão contrato próprio."""
from __future__ import annotations

from functools import reduce
from pathlib import Path, PurePosixPath
import re

import yaml

from src.pipelines.download_home_credit import sha256
from src.profiling.frame_profile import profile_frame, profile_base


def load_contract(path: Path) -> dict:
    contract = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(contract, dict) or contract.get('version') != 1:
        raise ValueError('Contrato deve declarar version: 1')
    tables = contract.get('tables')
    if not isinstance(tables, dict) or 'train_base' not in tables:
        raise ValueError('Contrato deve conter tables e train_base')
    sources = contract.get('sources')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('Contrato deve fixar os fingerprints das origens')
    for filename, fingerprint in sources.items():
        relative = PurePosixPath(filename)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or '\\' in filename:
            raise ValueError('Caminho inválido em sources')
        if (not isinstance(fingerprint, dict)
                or not re.fullmatch(r'[0-9a-f]{64}', str(fingerprint.get('sha256', '')))
                or type(fingerprint.get('bytes')) is not int or fingerprint['bytes'] < 0):
            raise ValueError(f'Fingerprint inválido: {filename}')
    for name, table in tables.items():
        schema, key = table.get('schema'), table.get('key')
        non_null = table.get('required_non_null')
        if not isinstance(schema, dict) or not schema:
            raise ValueError(f'Schema ausente: {name}')
        if (not isinstance(key, list) or not key or len(key) != len(set(key))
                or not set(key) <= set(schema)):
            raise ValueError(f'Chave inválida: {name}')
        if not isinstance(non_null, list) or not set(key) <= set(non_null) <= set(schema):
            raise ValueError(f'Regras de nulabilidade inválidas: {name}')
        if type(table.get('minimum_rows')) is not int or table['minimum_rows'] < 0:
            raise ValueError(f'minimum_rows inválido: {name}')
        if not isinstance(table.get('files'), list) or not table['files']:
            raise ValueError(f'Arquivos ausentes: {name}')
        for filename in table['files']:
            rel = PurePosixPath(filename)
            if rel.is_absolute() or '..' in rel.parts or '\\' in filename:
                raise ValueError(f'Caminho inválido no contrato: {name}')
            if filename not in sources:
                raise ValueError(f'Arquivo sem fingerprint no contrato: {filename}')
        reference = table.get('reference')
        if reference:
            parent = tables.get(reference.get('table'), {})
            columns = reference.get('columns', [])
            if not columns or not set(columns) <= set(schema) & set(parent.get('schema', {})):
                raise ValueError(f'Referência inválida: {name}')
            if any(schema[c] != parent['schema'][c] for c in columns):
                raise ValueError(f'Tipos incompatíveis na referência: {name}')
    return contract


def check_schema(df, specification: dict):
    actual = dict(df.dtypes)
    expected = specification['schema']
    if actual != expected:
        missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
        changed = {c: {'expected': expected[c], 'actual': actual[c]}
                   for c in set(expected) & set(actual) if expected[c] != actual[c]}
        raise ValueError(f'Schema incompatível: missing={missing}, extra={extra}, types={changed}')


def source_fingerprints(raw: Path, contract: dict) -> dict:
    result = {}
    for filename, expected in contract['sources'].items():
        path = (raw / filename).resolve()
        if not path.is_relative_to(raw.resolve()) or not path.is_file():
            raise ValueError(f'Origem ausente ou fora da RAW: {filename}')
        actual = {'sha256': sha256(path), 'bytes': path.stat().st_size}
        if actual != expected:
            raise ValueError(f'Snapshot de origem diferente do contrato: {filename}')
        result[filename] = actual
    return result


def read_source_frames(spark, raw: Path, contract: dict) -> dict:
    frames = {}
    for name, specification in contract['tables'].items():
        shards = []
        for filename in specification['files']:
            path = (raw / filename).resolve()
            if not path.is_relative_to(raw.resolve()) or not path.is_file():
                raise ValueError(f'Shard obrigatório ausente: {filename}')
            shard = spark.read.parquet(str(path))
            check_schema(shard, specification)
            shards.append(shard)
        frames[name] = reduce(lambda a, b: a.unionByName(b), shards)
    return frames


def validate_snapshot(frames: dict, contract: dict) -> dict:
    from pyspark.sql import functions as F

    if set(frames) != set(contract['tables']):
        raise ValueError('O conjunto de tabelas não corresponde ao contrato')
    profiles, checks = {}, []
    for name, specification in contract['tables'].items():
        frame = frames[name]
        check_schema(frame, specification)
        profile = profile_frame(frame, specification['key'])
        profiles[name] = profile
        nulls = {c['column']: c['null_count'] for c in profile['schema']}
        checks.extend([
            {'table': name, 'check': 'minimum_rows', 'success': profile['rows'] >= specification['minimum_rows']},
            {'table': name, 'check': 'unique_key', 'success': profile['duplicate_key_groups'] == 0},
            {'table': name, 'check': 'required_non_null',
             'success': all(nulls[c] == 0 for c in specification['required_non_null'])},
        ])
        reference = specification.get('reference')
        if reference:
            columns = reference['columns']
            child = frame.select(*columns).distinct()
            parent = frames[reference['table']].select(*columns).distinct()
            orphans = child.join(parent, columns, 'left_anti').count()
            missing = parent.join(child, columns, 'left_anti').count()
            profile.update(orphan_keys=orphans, parent_keys_without_match=missing)
            checks.append({'table': name, 'check': 'foreign_key', 'success': orphans == 0})
            if reference['full_coverage']:
                checks.append({'table': name, 'check': 'parent_coverage', 'success': missing == 0})
    base = frames['train_base']
    base_profile = profile_base(base)
    canonical_dates = base.filter(~F.col('date_decision').rlike(r'^\d{4}-\d{2}-\d{2}$')).limit(1).count() == 0
    checks.extend([
        {'table': 'train_base', 'check': 'valid_iso_date',
         'success': base_profile['invalid_dates'] == 0 and canonical_dates},
        {'table': 'train_base', 'check': 'month_matches_date', 'success': base_profile['month_mismatches'] == 0},
        {'table': 'train_base', 'check': 'target_domain', 'success': base_profile['invalid_targets'] == 0},
        {'table': 'train_base', 'check': 'non_negative_week', 'success': base_profile['min_week'] is not None and base_profile['min_week'] >= 0},
    ])
    return {'status': 'passed' if all(c['success'] for c in checks) else 'failed',
            'checks': checks, 'tables': profiles, 'base': base_profile}
