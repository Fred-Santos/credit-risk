"""Contratos e oráculos SQL independentes para ABT e indicadores."""
from functools import reduce
import uuid

from src.gold.model import ABT_SCHEMA, MONTH_SCHEMA
from src.quality.contracts import check_schema
from src.quality.reconcile_bronze import compare_rows


class GoldQualityError(RuntimeError):
    def __init__(self, report):
        super().__init__('Qualidade/reconciliação Gold reprovada')
        self.report = report


def _oracle_sql(views: dict):
    b, s, h = (views[n] for n in ('credit_cases', 'credit_static', 'previous_applications'))
    return f"""WITH hist AS (
      SELECT case_id, COUNT(*) AS n, COUNT(credamount_590A) AS filled,
        SUM(credamount_590A) AS amount_sum, AVG(credamount_590A) AS amount_mean,
        MIN(credamount_590A) AS amount_min, MAX(credamount_590A) AS amount_max,
        MAX(_source_revision) AS revision FROM `{h}` GROUP BY case_id)
      SELECT b.case_id,b.date_decision,b.MONTH,b.WEEK_NUM,b.target,
        s.annuity_780A AS static_annuity,(s.case_id IS NOT NULL) AS has_static,
        (COALESCE(h.n,0L)>0) AS has_previous_applications,
        COALESCE(h.n,0L) AS previous_application_count,
        COALESCE(h.filled,0L) AS previous_amount_non_null_count,
        h.amount_sum AS previous_amount_sum,h.amount_mean AS previous_amount_mean,
        h.amount_min AS previous_amount_min,h.amount_max AS previous_amount_max,
        b._source_revision AS case_source_revision,s._source_revision AS static_source_revision,
        h.revision AS previous_max_source_revision,
        (COALESCE(b._source_revision,0L)>1 OR COALESCE(s._source_revision,0L)>1
         OR COALESCE(h.revision,0L)>1) AS has_revised_source,
        CAST(1 AS INT) AS _abt_contract_version
      FROM `{b}` b LEFT JOIN `{s}` s ON b.case_id=s.case_id LEFT JOIN hist h ON b.case_id=h.case_id"""


def validate_abt(abt, silver: dict, spec: dict):
    from pyspark.sql import functions as F
    check_schema(abt, {'schema': spec['schemas']['abt']})
    checks = []

    def record(name, success, **details):
        checks.append({'check': name, 'success': bool(success), **details})

    required = ['case_id', 'date_decision', 'MONTH', 'WEEK_NUM', 'has_static', 'has_previous_applications',
                'previous_application_count', 'previous_amount_non_null_count', 'case_source_revision',
                'has_revised_source', '_abt_contract_version']
    nulls = reduce(lambda a, b: a | b, [F.col(c).isNull() for c in required])
    rows = abt.count()
    record('required_non_null', not abt.filter(nulls).limit(1).count())
    record('one_row_per_case', rows == silver['credit_cases'].count()
           and not abt.groupBy('case_id').count().filter('count > 1').limit(1).count())
    record('target_domain', not abt.filter(F.col('target').isNotNull() & ~F.col('target').isin(0, 1)).limit(1).count())
    record('contract_version', not abt.filter(F.col('_abt_contract_version') != 1).limit(1).count())
    record('count_bounds', not abt.filter((F.col('previous_application_count') < 0)
        | (F.col('previous_amount_non_null_count') < 0)
        | (F.col('previous_amount_non_null_count') > F.col('previous_application_count'))).limit(1).count())
    finite = [F.isnan(c) | (F.abs(F.col(c)) == float('inf')) for c in
              ('static_annuity', 'previous_amount_sum', 'previous_amount_mean', 'previous_amount_min', 'previous_amount_max')]
    record('finite_amounts', not abt.filter(reduce(lambda a, b: a | b, finite)).limit(1).count())
    views = {name: 'oracle_' + uuid.uuid4().hex for name in silver}
    spark = abt.sparkSession
    for name, frame in silver.items():
        frame.createOrReplaceTempView(views[name])
    try:
        expected = spark.sql(_oracle_sql(views))
        exact = [c for c in ABT_SCHEMA if c not in ('previous_amount_sum', 'previous_amount_mean')]
        proof = compare_rows(expected.select(*exact), abt.select(*exact), exact)
        record('sql_oracle_exact_columns', **proof)
        paired = abt.alias('a').join(expected.alias('e'), 'case_id', 'inner')
        for c in ('previous_amount_sum', 'previous_amount_mean'):
            actual, reference = F.col('a.' + c), F.col('e.' + c)
            bad = (actual.isNull() != reference.isNull()) | (
                actual.isNotNull() & reference.isNotNull() &
                (F.abs(actual - reference) > F.greatest(F.lit(spec['amount_oracle_absolute_tolerance']),
                    F.abs(reference) * spec['amount_oracle_relative_tolerance'])))
            record('sql_oracle_' + c, not paired.filter(bad).limit(1).count())
    finally:
        for view in views.values():
            spark.catalog.dropTempView(view)
    report = {'status': 'passed' if all(c['success'] for c in checks) else 'failed',
              'checks': checks, 'rows': rows, 'grain': 'case_id', 'discarded_rows': 0}
    if report['status'] != 'passed':
        raise GoldQualityError(report)
    return report


def validate_monthly(monthly, abt, silver: dict, spec: dict):
    """Reconciliar numeradores/denominadores diretamente com as tabelas Silver."""
    check_schema(monthly, {'schema': spec['schemas']['monthly_metrics']})
    from pyspark.sql import functions as F
    b, s, h = (silver[n] for n in ('credit_cases', 'credit_static', 'previous_applications'))
    history = h.groupBy('case_id').agg(F.count('*').alias('n'), F.count('credamount_590A').alias('filled'))
    population = (b.select('case_id', 'MONTH', 'target')
        .join(s.select('case_id').withColumn('covered_static', F.lit(1)), 'case_id', 'left')
        .join(history, 'case_id', 'left'))
    counts = population.groupBy('MONTH').agg(F.count('*').alias('case_count'),
        F.sum(F.when(F.col('target').isin(0, 1), 1).otherwise(0)).cast('long').alias('valid_label_count'),
        F.sum(F.when(F.col('target') == 1, 1).otherwise(0)).cast('long').alias('target_1_count'),
        F.sum(F.coalesce(F.col('covered_static'), F.lit(0))).cast('long').alias('static_covered_count'),
        F.sum(F.when(F.col('n') > 0, 1).otherwise(0)).cast('long').alias('history_covered_count'),
        F.sum(F.coalesce(F.col('n'), F.lit(0))).cast('long').alias('history_row_count'),
        F.sum(F.coalesce(F.col('filled'), F.lit(0))).cast('long').alias('history_amount_non_null_count'))
    expected = (counts.withColumn('target_1_rate', F.when(F.col('valid_label_count') > 0,
                    F.col('target_1_count').cast('double') / F.col('valid_label_count')))
        .withColumn('static_coverage_rate', F.col('static_covered_count').cast('double') / F.col('case_count'))
        .withColumn('history_coverage_rate', F.col('history_covered_count').cast('double') / F.col('case_count')))
    proof = compare_rows(expected.select(*MONTH_SCHEMA), monthly, list(MONTH_SCHEMA))
    valid = proof['success'] and not monthly.groupBy('MONTH').count().filter('count > 1').limit(1).count()
    if monthly.agg(F.sum('case_count')).first()[0] not in (abt.count(), None):
        valid = False
    report = {'status': 'passed' if valid else 'failed', 'oracle': 'silver_direct_counts_not_abt',
              'proof': proof, 'periods': monthly.count()}
    if not valid:
        raise GoldQualityError(report)
    return report
