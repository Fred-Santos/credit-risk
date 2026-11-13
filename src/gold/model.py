"""Agregação 1:N antes do join; números da fonte sem imputação ou arredondamento."""
from pathlib import Path

import yaml

from src.pipelines.download_home_credit import sha256

ABT_SCHEMA = {'case_id': 'bigint', 'date_decision': 'date', 'MONTH': 'bigint', 'WEEK_NUM': 'bigint',
    'target': 'bigint', 'static_annuity': 'double', 'has_static': 'boolean',
    'has_previous_applications': 'boolean', 'previous_application_count': 'bigint',
    'previous_amount_non_null_count': 'bigint', 'previous_amount_sum': 'double',
    'previous_amount_mean': 'double', 'previous_amount_min': 'double', 'previous_amount_max': 'double',
    'case_source_revision': 'bigint', 'static_source_revision': 'bigint', 'previous_max_source_revision': 'bigint',
    'has_revised_source': 'boolean', '_abt_contract_version': 'int'}
MONTH_SCHEMA = {'MONTH': 'bigint', 'case_count': 'bigint', 'valid_label_count': 'bigint',
    'target_1_count': 'bigint', 'target_1_rate': 'double', 'static_covered_count': 'bigint',
    'static_coverage_rate': 'double', 'history_covered_count': 'bigint', 'history_coverage_rate': 'double',
    'history_row_count': 'bigint', 'history_amount_non_null_count': 'bigint'}


def load_gold_contract(path: Path, silver: Path) -> dict:
    spec = yaml.safe_load(path.read_text())
    expected = {'version': 1, 'scope': 'retrospective_credit_analytics',
        'silver_contract_sha256': sha256(silver), 'abt_grain': 'one_row_per_case_id',
        'history_aggregation': 'all_observations_per_case_before_join',
        'amount_arithmetic': 'deterministic_double_fold_sorted_by_num_group1_no_rounding',
        'amount_oracle_absolute_tolerance': 1e-8, 'amount_oracle_relative_tolerance': 1e-12,
        'missing_history': 'zero_counts_false_flag_null_amounts_and_revision',
        'all_null_amounts': 'zero_non_null_count_null_sum_mean_min_max',
        'label_denominator': 'target_in_0_or_1_null_excluded', 'zero_denominator': 'null_rate',
        'empty_population': 'no_synthetic_period_rows', 'temporal_availability': 'retrospective_not_point_in_time',
        'incremental_scope': 'case_ids_changed_in_any_silver_table_and_old_new_months',
        'case_removal': 'fail_no_implicit_delete', 'schemas': {'abt': ABT_SCHEMA, 'monthly_metrics': MONTH_SCHEMA}}
    if spec != expected or type(spec.get('version')) is not int:
        raise ValueError('Contrato Gold v1 inválido ou regra não suportada')
    return {**spec, 'contract_sha256': sha256(path)}


def build_abt(silver: dict, case_ids=None):
    from pyspark.sql import functions as F
    base, static, history = (silver[n] for n in ('credit_cases', 'credit_static', 'previous_applications'))
    if case_ids is not None:
        base = base.join(case_ids, 'case_id', 'left_semi')
        static = static.join(case_ids, 'case_id', 'left_semi')
        history = history.join(case_ids, 'case_id', 'left_semi')
    observations = F.sort_array(F.collect_list(F.struct(F.col('num_group1').alias('i'),
                                                       F.col('credamount_590A').alias('v'))))
    ordered_sum = F.aggregate(observations, F.lit(0.0),
                              lambda acc, row: acc + F.coalesce(row['v'], F.lit(0.0)))
    historical = history.groupBy('case_id').agg(
        F.count('*').alias('previous_application_count'),
        F.count('credamount_590A').alias('previous_amount_non_null_count'),
        ordered_sum.alias('_ordered_sum'), F.min('credamount_590A').alias('previous_amount_min'),
        F.max('credamount_590A').alias('previous_amount_max'),
        F.max('_source_revision').alias('previous_max_source_revision'))
    base = base.select('case_id', 'date_decision', 'MONTH', 'WEEK_NUM', 'target',
                       F.col('_source_revision').alias('case_source_revision'))
    static = static.select('case_id', F.col('annuity_780A').alias('static_annuity'),
                           F.lit(True).alias('has_static'), F.col('_source_revision').alias('static_source_revision'))
    result = base.join(static, 'case_id', 'left').join(historical, 'case_id', 'left')
    result = (result.withColumn('has_static', F.coalesce(F.col('has_static'), F.lit(False)))
        .withColumn('previous_application_count', F.coalesce(F.col('previous_application_count'), F.lit(0).cast('long')))
        .withColumn('previous_amount_non_null_count', F.coalesce(F.col('previous_amount_non_null_count'), F.lit(0).cast('long')))
        .withColumn('has_previous_applications', F.col('previous_application_count') > 0)
        .withColumn('previous_amount_sum', F.when(F.col('previous_amount_non_null_count') > 0, F.col('_ordered_sum')))
        .withColumn('previous_amount_mean', F.when(F.col('previous_amount_non_null_count') > 0,
            F.col('_ordered_sum') / F.col('previous_amount_non_null_count')))
        .withColumn('has_revised_source', (F.coalesce(F.col('case_source_revision'), F.lit(0)) > 1)
            | (F.coalesce(F.col('static_source_revision'), F.lit(0)) > 1)
            | (F.coalesce(F.col('previous_max_source_revision'), F.lit(0)) > 1))
        .withColumn('_abt_contract_version', F.lit(1).cast('int')))
    return result.select(*ABT_SCHEMA)


def monthly_sql(view: str) -> str:
    return f"""WITH counts AS (
      SELECT MONTH, COUNT(*) AS case_count,
        SUM(CASE WHEN target IN (0,1) THEN 1L ELSE 0L END) AS valid_label_count,
        SUM(CASE WHEN target=1 THEN 1L ELSE 0L END) AS target_1_count,
        SUM(CASE WHEN has_static THEN 1L ELSE 0L END) AS static_covered_count,
        SUM(CASE WHEN has_previous_applications THEN 1L ELSE 0L END) AS history_covered_count,
        SUM(previous_application_count) AS history_row_count,
        SUM(previous_amount_non_null_count) AS history_amount_non_null_count
      FROM `{view}` GROUP BY MONTH)
      SELECT MONTH, case_count, valid_label_count, target_1_count,
        CASE WHEN valid_label_count=0 THEN CAST(NULL AS DOUBLE)
             ELSE CAST(target_1_count AS DOUBLE)/valid_label_count END AS target_1_rate,
        static_covered_count, CAST(static_covered_count AS DOUBLE)/case_count AS static_coverage_rate,
        history_covered_count, CAST(history_covered_count AS DOUBLE)/case_count AS history_coverage_rate,
        history_row_count, history_amount_non_null_count FROM counts"""


def build_monthly(abt):
    import uuid
    view = 'abt_metrics_' + uuid.uuid4().hex
    abt.createOrReplaceTempView(view)
    try:
        result = abt.sparkSession.sql(monthly_sql(view))
        _ = result.schema  # Analisar enquanto a view existe; o plano guarda a relação resolvida.
        return result.select(*MONTH_SCHEMA)
    finally:
        abt.sparkSession.catalog.dropTempView(view)


def affected_cases(previous: dict, current: dict):
    from functools import reduce
    from src.quality.contracts import check_schema
    base = 'credit_cases'
    if previous[base].select('case_id').join(current[base].select('case_id'), 'case_id', 'left_anti').limit(1).count():
        raise ValueError('Remoção de casos não autorizada na Gold incremental')
    changes = []
    for name, old in previous.items():
        new = current[name]
        check_schema(new, {'schema': dict(old.dtypes)})
        columns = old.columns
        changes.extend([new.select(*columns).exceptAll(old.select(*columns)).select('case_id'),
                        old.select(*columns).exceptAll(new.select(*columns)).select('case_id')])
    return reduce(lambda a, b: a.unionByName(b), changes).distinct()
