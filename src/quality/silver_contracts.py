"""Contratos do estado Silver: definição independente dos schemas auto declarados pelo writer."""
from __future__ import annotations

from functools import reduce
from pathlib import Path

import yaml

from src.pipelines.download_home_credit import sha256
from src.silver.initial_delta import TABLES
from src.silver.transforms import load_silver_policy, _schemas

POLICIES = {'schema_drift': 'fail', 'missing_or_extra_tables': 'fail',
            'required_nulls': 'fail', 'optional_nulls': 'preserve',
            'rule_failure': 'block_whole_validation_no_drop', 'metadata_strings': 'non_blank',
            'auxiliary_date_availability': 'measure_only_retrospective',
            'history_maximum_per_case': 'not_imposed'}
DOMAINS = {'target': [0, 1], 'WEEK_NUM_minimum': 0,
           'MONTH_matches_date_decision': True, 'num_group1_minimum': 0}
RELATIONSHIPS = {
    'credit_static': {'parent': 'credit_cases', 'columns': ['case_id'],
                      'cardinality': 'one_to_one', 'full_parent_coverage': True},
    'previous_applications': {'parent': 'credit_cases', 'columns': ['case_id'],
                             'cardinality': 'many_to_one', 'full_parent_coverage': False}}
METADATA_NAMES = ['_run_id', '_ingest_date', '_source_file', 'ingest_batch']


class SilverContractError(RuntimeError):
    def __init__(self, report):
        super().__init__('Contratos Silver reprovados; nenhuma publicação aprovada')
        self.report = report


def load_silver_contract(path: Path, snapshot: Path, policy: Path, notebook: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    if (not isinstance(config, dict) or set(config) != {
            'version', 'scope', 'snapshot_contract_sha256', 'silver_policy_sha256',
            'schema_derivation', 'table_bindings', 'policies', 'domains', 'relationships'}
            or type(config['version']) is not int or config['version'] != 1
            or config['scope'] != 'silver_initial_persisted'
            or config['schema_derivation'] != 'snapshot_with_policy_dates_and_bronze_metadata_v1'
            or config['table_bindings'] != {target: source for source, target in TABLES.items()}
            or config['policies'] != POLICIES or config['domains'] != DOMAINS
            or config['relationships'] != RELATIONSHIPS):
        raise ValueError('Contrato Silver v1 inválido ou regras não suportadas')
    if config['snapshot_contract_sha256'] != sha256(snapshot) or config['silver_policy_sha256'] != sha256(policy):
        raise ValueError('Contrato Silver desvinculado do snapshot/política')
    silver_policy, source = load_silver_policy(policy, snapshot, notebook)
    plan = {'version': 1, 'contract_sha256': sha256(path),
            'snapshot_contract_sha256': sha256(snapshot), 'silver_policy_sha256': sha256(policy),
            'policies': config['policies'], 'domains': config['domains'], 'tables': {}}
    for origin, target in TABLES.items():
        spec = source['tables'][origin]
        dates = silver_policy['tables'][origin]['cast_to_date']
        _, schema = _schemas(spec, dates)
        relationship = config['relationships'].get(target)
        reference = spec.get('reference')
        if relationship and (not reference or TABLES[reference['table']] != relationship['parent']
                             or reference['columns'] != relationship['columns']
                             or reference['full_coverage'] != relationship['full_parent_coverage']):
            raise ValueError('Relacionamento Silver incompatível com o contrato de origem')
        plan['tables'][target] = {'source_table': origin, 'grain': spec['grain'], 'schema': schema,
            'key': spec['key'], 'required_non_null': spec['required_non_null'] + METADATA_NAMES,
            'minimum_rows': spec['minimum_rows'], 'dates': dates, 'relationship': relationship}
    return plan


def validate_silver_frames(frames: dict, plan: dict, expected_counts: dict | None = None) -> dict:
    from pyspark.sql import functions as F

    report = {'status': 'running', 'checks': [], 'tables': {}, 'relationships': {},
              'accepted_rows': 0, 'discarded_rows': 0,
              'temporal_availability': 'unverified_retrospective_only'}

    def check(table, name, success, **details):
        report['checks'].append({'table': table, 'check': name, 'success': bool(success), **details})

    check('*', 'table_set', set(frames) == set(plan['tables']), expected=sorted(plan['tables']), actual=sorted(frames))
    if expected_counts is not None and set(expected_counts) != set(plan['tables']):
        raise ValueError('Contagens esperadas devem abranger exatamente as tabelas do contrato')
    valid_schemas = set()
    for name, spec in plan['tables'].items():
        if name not in frames:
            check(name, 'dataset_present', False)
            continue
        frame = frames[name]
        actual, expected = dict(frame.dtypes), spec['schema']
        schema_ok = actual == expected
        check(name, 'exact_schema', schema_ok,
              missing_columns=sorted(set(expected) - set(actual)), extra_columns=sorted(set(actual) - set(expected)),
              type_mismatches={c: {'actual': actual[c], 'expected': expected[c]}
                               for c in set(expected) & set(actual) if actual[c] != expected[c]})
        if not schema_ok:
            continue  # Relações dependentes serão explicitamente reprovadas, sem casts defensivos.
        valid_schemas.add(name)
        columns = list(expected)
        expressions = [F.count('*').alias('rows'), F.countDistinct('case_id').alias('distinct_cases')]
        expressions += [F.sum(F.col(c).isNull().cast('long')).alias(f'n{i}') for i, c in enumerate(columns)]
        for i, c in enumerate(spec['dates']):
            expressions += [F.min(c).alias(f'dmin{i}'), F.max(c).alias(f'dmax{i}')]
        values = frame.agg(*expressions).first().asDict()
        nulls = {c: values[f'n{i}'] or 0 for i, c in enumerate(columns)}
        item = {'rows': values['rows'], 'distinct_cases': values['distinct_cases'], 'null_counts': nulls,
                'grain': spec['grain'], 'key': spec['key'],
                'date_ranges': {c: {'min': str(values[f'dmin{i}']) if values[f'dmin{i}'] is not None else None,
                                   'max': str(values[f'dmax{i}']) if values[f'dmax{i}'] is not None else None}
                                for i, c in enumerate(spec['dates'])}}
        report['tables'][name] = item
        check(name, 'minimum_rows', item['rows'] >= spec['minimum_rows'], minimum=spec['minimum_rows'])
        if expected_counts is not None:
            check(name, 'selection_row_count', item['rows'] == expected_counts[name], expected=expected_counts[name])
        check(name, 'required_non_null', not any(nulls[c] for c in spec['required_non_null']))
        duplicates = frame.groupBy(*spec['key']).count().filter('count > 1').count()
        item['duplicate_key_groups'] = duplicates
        check(name, 'unique_key', duplicates == 0, duplicate_groups=duplicates)
        blank = reduce(lambda a, b: a | b, [F.length(F.trim(F.col(c))) == 0
                                          for c in ['_run_id', '_source_file', 'ingest_batch']])
        check(name, 'non_blank_metadata', frame.filter(blank).limit(1).count() == 0)
        if name == 'credit_cases':
            bad_target = F.col('target').isNull() | ~F.col('target').isin(plan['domains']['target'])
            check(name, 'target_domain', frame.filter(bad_target).count() == 0)
            check(name, 'non_negative_week', frame.filter(F.col('WEEK_NUM').isNull() |
                  (F.col('WEEK_NUM') < plan['domains']['WEEK_NUM_minimum'])).count() == 0)
            bad_month = ~F.col('MONTH').eqNullSafe(F.date_format('date_decision', 'yyyyMM').cast('long'))
            check(name, 'month_matches_decision', frame.filter(bad_month).count() == 0)
        if name == 'previous_applications':
            bad_group = F.col('num_group1').isNull() | (F.col('num_group1') < plan['domains']['num_group1_minimum'])
            check(name, 'non_negative_group_index', frame.filter(bad_group).count() == 0)
    for name, spec in plan['tables'].items():
        ref = spec['relationship']
        if not ref:
            continue
        parent = ref['parent']
        if name not in valid_schemas or parent not in valid_schemas:
            check(name, 'relationship_inputs_valid', False, parent=parent)
            continue
        child, base, keys = frames[name], frames[parent], ref['columns']
        child_keys, base_keys = child.select(*keys).distinct(), base.select(*keys).distinct()
        orphans = child_keys.join(base_keys, keys, 'left_anti').count()
        missing = base_keys.join(child_keys, keys, 'left_anti').count()
        child_join_rows = child.select(*keys).join(base.select(*keys), keys, 'left').count()
        base_join_rows = base.select(*keys).join(child.select(*keys), keys, 'left').count()
        distribution = child.groupBy(*keys).count().agg(F.min('count').alias('minimum'), F.max('count').alias('maximum')).first()
        metrics = {'parent': parent, 'orphan_keys': orphans, 'parent_keys_without_match': missing,
                   'cardinality': ref['cardinality'], 'child_left_join_rows': child_join_rows,
                   'base_left_join_rows': base_join_rows,
                   'min_rows_per_covered_case': distribution['minimum'],
                   'max_rows_per_covered_case': distribution['maximum']}
        report['relationships'][name] = metrics
        check(name, 'foreign_key', orphans == 0, orphan_keys=orphans)
        check(name, 'many_to_one_parent', child_join_rows == report['tables'][name]['rows'])
        if ref['full_parent_coverage']:
            check(name, 'full_parent_coverage', missing == 0, missing_parent_keys=missing)
        if ref['cardinality'] == 'one_to_one':
            check(name, 'one_to_one_cardinality', base_join_rows == report['tables'][parent]['rows'])
        # Somente diagnóstico: a existência de datas posteriores não vira filtro ou falha.
        temporal = child.select(*keys, *spec['dates']).join(base.select(*keys, 'date_decision'), keys, 'inner')
        if spec['dates']:
            measured = temporal.agg(*[F.sum((F.col(c) > F.col('date_decision')).cast('long')).alias(f'a{i}')
                                      for i, c in enumerate(spec['dates'])]).first()
            metrics['auxiliary_dates_after_decision'] = {c: measured[f'a{i}'] or 0 for i, c in enumerate(spec['dates'])}
            metrics['temporal_check_role'] = 'diagnostic_only_not_point_in_time_proof'
    report['status'] = 'passed' if all(c['success'] for c in report['checks']) else 'failed'
    if report['status'] != 'passed':
        raise SilverContractError(report)
    report['accepted_rows'] = sum(t['rows'] for t in report['tables'].values())
    return report
