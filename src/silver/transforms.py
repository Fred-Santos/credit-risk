"""Tratamento Silver v1: datas ISO com guarda de perda, sem escrita de tabelas."""
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import yaml

from src.pipelines.download_home_credit import sha256
from src.quality.bronze_contract import METADATA
from src.quality.contracts import check_schema, load_contract
from src.quality.reconcile_bronze import compare_rows

POLICIES = {
    'input': 'approved_bronze_snapshot', 'grain': 'preserve_each_source_table',
    'date_cast': 'iso_date_with_zero_new_nulls_or_block', 'numeric_types': 'preserve_source_types',
    'optional_nulls': 'preserve', 'sentinel_replacement': 'none_without_semantic_evidence',
    'coded_strings': 'preserve_all_formats', 'column_drop': 'none', 'boolean_null_to_false': False,
    'deduplication': 'none_fail_on_key_violation',
    'historical_join_to_case': 'deferred_aggregate_before_gold_join',
    'target': 'retrospective_only_no_resampling',
}


class SilverTransformError(ValueError):
    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


def load_silver_policy(path: Path, snapshot_path: Path, notebook_path: Path) -> tuple[dict, dict]:
    policy = yaml.safe_load(path.read_text())
    if (not isinstance(policy, dict) or set(policy) != {
            'version', 'scope', 'implementation_status', 'snapshot_contract_sha256',
            'notebook_sha256', 'policies', 'tables'}
            or type(policy['version']) is not int or policy['version'] != 1
            or policy['scope'] != 'silver_initial'
            or policy['implementation_status'] != 'transformations_implemented'
            or policy['policies'] != POLICIES
            or policy['policies'].get('boolean_null_to_false') is not False):
        raise ValueError('Política Silver não suportada pelo transformador v1')
    if policy['snapshot_contract_sha256'] != sha256(snapshot_path) or policy['notebook_sha256'] != sha256(notebook_path):
        raise ValueError('Política diverge do contrato ou notebook revisados')
    contract = load_contract(snapshot_path)
    if not isinstance(policy['tables'], dict) or set(policy['tables']) != set(contract['tables']):
        raise ValueError('Tabelas da política divergem do contrato')
    for name, spec in contract['tables'].items():
        rule = policy['tables'][name]
        dates = rule.get('cast_to_date') if isinstance(rule, dict) else None
        # O contrato fixado contém as datas revisadas em F03.1. Não inferir
        # tratamento só pelo sufixo em um contrato futuro ou arquivo novo.
        approved = {c for c, dtype in spec['schema'].items()
                    if dtype == 'string' and (c.endswith('D') or c == 'date_decision')}
        if (not isinstance(rule, dict) or set(rule) != {'key', 'cast_to_date'}
                or rule['key'] != spec['key'] or not isinstance(dates, list)
                or any(not isinstance(c, str) for c in dates)
                or len(dates) != len(set(dates)) or set(dates) != approved):
            raise ValueError(f'Campos/chave da política divergentes: {name}')
    return policy, contract


def _schemas(spec: dict, dates: list[str]) -> tuple[dict, dict]:
    source = {**spec['schema'], **METADATA}
    if len(dates) != len(set(dates)) or any(source.get(c) != 'string' or c in METADATA for c in dates):
        raise ValueError('Conversão deve apontar apenas para campos string de negócio únicos')
    return source, {c: 'date' if c in dates else dtype for c, dtype in source.items()}


def transform_table(name: str, frame, spec: dict, dates: list[str]):
    from pyspark.sql import functions as F

    if frame.sparkSession.conf.get('spark.sql.session.timeZone') != 'UTC':
        raise ValueError('Transformador de datas v1 exige spark.sql.session.timeZone=UTC')
    source_schema, target_schema = _schemas(spec, dates)
    check_schema(frame, {'schema': source_schema})
    expressions, aggregates, invalid_conditions = {}, [F.count('*').alias('rows')], []
    metrics_names = ['input_nulls', 'invalid_shape', 'parse_failed', 'roundtrip_mismatch',
                     'new_nulls', 'output_nulls', 'converted_non_nulls']
    for index, column in enumerate(dates):
        c = F.col(column)
        iso = c.rlike(r'^\d{4}-\d{2}-\d{2}$')
        parsed = F.when(iso, F.try_to_timestamp(c, F.lit('yyyy-MM-dd')).cast('date'))
        same = F.date_format(parsed, 'yyyy-MM-dd') == c
        converted = F.when(iso & parsed.isNotNull() & same, parsed).otherwise(F.lit(None).cast('date'))
        expressions[column] = converted
        invalid = c.isNotNull() & converted.isNull()
        invalid_conditions.append(invalid)
        conditions = [c.isNull(), c.isNotNull() & ~iso, c.isNotNull() & iso & parsed.isNull(),
                      c.isNotNull() & iso & parsed.isNotNull() & ~same,
                      invalid, converted.isNull(), converted.isNotNull()]
        aggregates.extend(F.sum(condition.cast('long')).alias(f'd{index}_{metric}')
                          for metric, condition in zip(metrics_names, conditions))
    invalid_rows = reduce(lambda a, b: a | b, invalid_conditions, F.lit(False))
    aggregates.append(F.sum(invalid_rows.cast('long')).alias('invalid_rows'))
    values = frame.agg(*aggregates).first().asDict()
    report = {'table': name, 'input_rows': values['rows'], 'invalid_rows': values['invalid_rows'] or 0,
              'dates': {c: {metric: values[f'd{i}_{metric}'] or 0 for metric in metrics_names}
                        for i, c in enumerate(dates)}, 'status': 'passed'}
    report['invalid_date_cells'] = sum(d['new_nulls'] for d in report['dates'].values())
    if report['invalid_rows']:
        report['status'] = 'failed'
        raise SilverTransformError(f'Conversão de datas bloquearia publicação: {name}', report)
    transformed = frame.select(*[expressions[c].alias(c) if c in dates else F.col(c) for c in source_schema])
    check_schema(transformed, {'schema': target_schema})
    return transformed, report


def verify_transformation(before, after, spec: dict, dates: list[str]) -> dict:
    """Restaura apenas a representação das datas para comparar todos os valores."""
    from pyspark.sql import functions as F
    source_schema, target_schema = _schemas(spec, dates)
    check_schema(before, {'schema': source_schema})
    check_schema(after, {'schema': target_schema})
    restored = after.select(*[F.date_format(c, 'yyyy-MM-dd').alias(c) if c in dates else F.col(c)
                              for c in source_schema])
    return compare_rows(before, restored, list(source_schema))


@dataclass
class TransformedSilver:
    frames: dict
    report: dict


def transform_snapshot(frames: dict, contract: dict, policy: dict) -> TransformedSilver:
    if set(frames) != set(contract['tables']) or set(policy['tables']) != set(frames):
        raise ValueError('Conjunto de tabelas fora do contrato/política')
    transformed = {}
    report = {'status': 'running', 'tables': {}, 'accepted_rows': 0, 'discarded_rows': 0,
              'failure_policy': 'block_entire_publication_no_silent_drop'}
    for name, spec in contract['tables'].items():
        dates = policy['tables'][name]['cast_to_date']
        try:
            result, metrics = transform_table(name, frames[name], spec, dates)
        except SilverTransformError as error:
            report['tables'][name] = error.report
            report['status'] = 'failed'
            raise SilverTransformError(str(error), report) from error
        report['tables'][name] = metrics
        proof = verify_transformation(frames[name], result, spec, dates)
        metrics['preservation'] = proof
        if not proof['success']:
            report['status'] = 'failed'
            raise SilverTransformError(f'Valores não preservados: {name}', report)
        transformed[name] = result
    report.update(status='passed', accepted_rows=sum(t['input_rows'] for t in report['tables'].values()))
    return TransformedSilver(transformed, report)
