"""Consultas descritivas e reconciliação independente; coletar só agregados."""
from calendar import monthrange
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import uuid

import yaml

from src.quality.reconcile_bronze import compare_rows


def load_analysis_policy(path: Path):
    policy = yaml.safe_load(path.read_text())
    expected = {'version': 1, 'scope': 'retrospective_published_gold_analysis',
        'population': 'all_case_ids_in_explicit_publication', 'valid_labels': [0, 1],
        'small_group_min_cases': 500, 'small_group_min_target_1': 20,
        'small_group_interpretation': 'reading_flags_not_significance_or_suppression',
        'partial_month': 'observed_date_bounds_do_not_span_calendar_month',
        'label_maturity': 'not_audited_no_point_in_time_or_operational_default_claim',
        'segments': ['no_history', 'one_observation', 'two_to_five', 'six_or_more'],
        'max_changed_cases_to_collect': 50,
        'amount_comparison': 'individual_changed_cases_no_population_monetary_sum',
        'charts': 'static_png_and_svg_from_aggregated_results', 'source_mutation': 'forbidden'}
    if policy != expected or any(type(policy[k]) is not int for k in
            ('version', 'small_group_min_cases', 'small_group_min_target_1', 'max_changed_cases_to_collect')):
        raise ValueError('Política analítica v1 inválida ou não suportada')
    return policy


@contextmanager
def sql_views(frames):
    names = {k: 'analysis_' + uuid.uuid4().hex for k in frames}
    spark = next(iter(frames.values())).sparkSession
    for key, frame in frames.items():
        frame.createOrReplaceTempView(names[key])
    try:
        yield spark, names
    finally:
        for name in names.values():
            spark.catalog.dropTempView(name)


def safe_rate(numerator, denominator):
    return numerator / denominator if denominator else None


def reading_flags(row, policy):
    return {'small_case_count': row['case_count'] < policy['small_group_min_cases'],
            'few_target_1': row['target_1_count'] < policy['small_group_min_target_1']}


def monthly_analysis(abt, monthly, policy):
    """SQL de consumo, independente da consulta materializadora Gold."""
    with sql_views({'abt': abt}) as (spark, names):
        counts = spark.sql(f'''SELECT MONTH, COUNT(*) AS case_count,
            COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count,
            COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count,
            COUNT(CASE WHEN has_static THEN 1 END) AS static_covered_count,
            COUNT(CASE WHEN has_previous_applications THEN 1 END) AS history_covered_count,
            SUM(previous_application_count) AS history_row_count,
            SUM(previous_amount_non_null_count) AS history_amount_non_null_count,
            MIN(date_decision) AS observed_first_date, MAX(date_decision) AS observed_last_date
            FROM `{names['abt']}` GROUP BY MONTH''')
        from pyspark.sql import functions as F
        expected = (counts.withColumn('target_1_rate', F.when(F.col('valid_label_count') > 0,
                F.col('target_1_count').cast('double') / F.col('valid_label_count')))
            .withColumn('static_coverage_rate', F.col('static_covered_count').cast('double') / F.col('case_count'))
            .withColumn('history_coverage_rate', F.col('history_covered_count').cast('double') / F.col('case_count')))
        proof = compare_rows(expected.select(*monthly.columns), monthly, monthly.columns)
        if not proof['success']:
            raise ValueError(f'Indicadores publicados divergem do SQL de consumo: {proof}')
        dates = {r.MONTH: r.asDict() for r in counts.select('MONTH', 'observed_first_date', 'observed_last_date').collect()}
        rows = []
        for row in monthly.orderBy('MONTH').collect():
            item = row.asDict()
            first, last = (dates[row.MONTH][k] for k in ('observed_first_date', 'observed_last_date'))
            year, month = divmod(row.MONTH, 100)
            item.update(observed_first_date=first.isoformat(), observed_last_date=last.isoformat(),
                observed_partial_month=(first > date(year, month, 1) or last < date(year, month, monthrange(year, month)[1])),
                missing_label_count=row.case_count-row.valid_label_count, **reading_flags(item, policy))
            rows.append(item)
    return rows, proof


def population_summary(abt):
    with sql_views({'abt': abt}) as (spark, names):
        result = spark.sql(f'''SELECT COUNT(*) AS case_count, COUNT(DISTINCT case_id) AS distinct_case_count,
            COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count,
            COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count,
            COUNT(CASE WHEN target IS NULL THEN 1 END) AS missing_label_count,
            COUNT(CASE WHEN target IS NOT NULL AND target NOT IN (0,1) THEN 1 END) AS invalid_label_count,
            COUNT(CASE WHEN has_static THEN 1 END) AS static_covered_count,
            COUNT(static_annuity) AS static_annuity_non_null_count,
            COUNT(CASE WHEN has_previous_applications THEN 1 END) AS history_covered_count,
            COUNT(CASE WHEN has_previous_applications AND previous_amount_non_null_count=0 THEN 1 END) AS history_all_amounts_null_cases,
            COALESCE(SUM(previous_application_count),0L) AS history_row_count,
            COALESCE(SUM(previous_amount_non_null_count),0L) AS history_amount_non_null_count,
            MIN(date_decision) AS first_date, MAX(date_decision) AS last_date
            FROM `{names['abt']}`''').first().asDict()
    if result['case_count'] != result['distinct_case_count'] or result['invalid_label_count']:
        raise ValueError('ABT inválida para análise: grão ou domínio do rótulo')
    for key in ('first_date','last_date'):
        result[key] = result[key].isoformat() if result[key] is not None else None
    for numerator, denominator, name in (
        ('target_1_count','valid_label_count','target_1_rate'),
        ('static_covered_count','case_count','static_coverage_rate'),
        ('static_annuity_non_null_count','case_count','static_annuity_completeness'),
        ('history_covered_count','case_count','history_coverage_rate'),
        ('history_amount_non_null_count','history_row_count','history_amount_completeness')):
        result[name] = safe_rate(result[numerator],result[denominator])
    return result


def history_segments(abt, policy):
    from pyspark.sql import functions as F
    grouped = (abt.withColumn('segment', F.when(F.col('previous_application_count')==0,'no_history')
        .when(F.col('previous_application_count')==1,'one_observation')
        .when(F.col('previous_application_count')<=5,'two_to_five').otherwise('six_or_more'))
        .groupBy('segment').agg(F.count('*').alias('case_count'),
            F.count(F.when(F.col('target').isin(0,1),1)).alias('valid_label_count'),
            F.count(F.when(F.col('target')==1,1)).alias('target_1_count')))
    with sql_views({'abt':abt}) as (spark,names):
        oracle = spark.sql(f'''SELECT CASE WHEN previous_application_count=0 THEN 'no_history'
            WHEN previous_application_count=1 THEN 'one_observation'
            WHEN previous_application_count BETWEEN 2 AND 5 THEN 'two_to_five' ELSE 'six_or_more' END AS segment,
            COUNT(*) AS case_count, COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count,
            COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count
            FROM `{names['abt']}` GROUP BY 1''')
        proof = compare_rows(oracle,grouped,grouped.columns)
    if not proof['success']:
        raise ValueError('Segmentos divergem do SQL independente')
    found={r.segment:r.asDict() for r in grouped.collect()}
    result=[]
    for name in policy['segments']:
        row=found.get(name,{'segment':name,'case_count':0,'valid_label_count':0,'target_1_count':0})
        row.update(target_1_rate=safe_rate(row['target_1_count'],row['valid_label_count']),
                   empty_group=row['case_count']==0, **reading_flags(row,policy))
        result.append(row)
    return result,proof


def compare_publications(before, after, *, kind, policy):
    """Comparação bounded: nunca coletar uma ABT inteira para apresentar mudanças."""
    from pyspark.sql import functions as F
    old,new=before['gold.abt'],after['gold.abt']
    old_ids,new_ids=old.select('case_id'),new.select('case_id')
    added=new_ids.join(old_ids,'case_id','left_anti')
    removed=old_ids.join(new_ids,'case_id','left_anti')
    adds,deletes=added.count(),removed.count()
    if deletes or (kind=='correction' and adds):
        raise ValueError('Comparação de correção exige a mesma população; atraso só permite inserções')
    common=old_ids.join(new_ids,'case_id','inner')
    old_common=old.join(common,'case_id','left_semi')
    new_common=new.join(common,'case_id','left_semi')
    fixed=['case_id','date_decision','MONTH','WEEK_NUM','target']
    population_proof=compare_rows(old_common.select(*fixed),new_common.select(*fixed),fixed)
    if not population_proof['success']:
        raise ValueError('Casos em comum mudaram período ou rótulo durante a comparação')
    changed=(new_common.select(*old.columns).exceptAll(old_common.select(*old.columns)).select('case_id').distinct())
    changed_count=changed.count()
    if kind=='late_arrival' and changed_count:
        raise ValueError('Chegada tardia alterou casos anteriores; comparar efeitos separadamente')
    if changed_count+adds>policy['max_changed_cases_to_collect']:
        raise ValueError('Mudanças excedem o limite explícito de apresentação')
    previous={r.case_id:r.asDict() for r in old.join(changed,'case_id','left_semi').collect()}
    changes=[]
    for row in new.join(changed,'case_id','left_semi').orderBy('case_id').collect():
        current=row.asDict()
        columns=[c for c in old.columns if previous[row.case_id][c]!=current[c]]
        changes.append({'case_id':row.case_id,'MONTH':row.MONTH,'columns':{
            c:{'before':previous[row.case_id][c],'after':current[c]} for c in columns}})
    inserted=[r.asDict() for r in new.join(added,'case_id','left_semi')
        .select('case_id','MONTH','target','previous_application_count').orderBy('case_id').collect()]
    old_months={r.MONTH:r.asDict() for r in before['gold.monthly_metrics'].collect()}
    new_months={r.MONTH:r.asDict() for r in after['gold.monthly_metrics'].collect()}
    month_changes=[{'MONTH':m,'before':old_months.get(m),'after':new_months.get(m)}
                   for m in sorted(set(old_months)|set(new_months)) if old_months.get(m)!=new_months.get(m)]
    return {'kind':kind,'before_cases':old.count(),'after_cases':new.count(),'added_cases':adds,
        'removed_cases':deletes,'changed_common_cases':changed_count,'stable_common_population':population_proof,
        'changed_cases':changes,'inserted_cases':inserted,'monthly_changes':month_changes,
        'monthly_unchanged':not month_changes}
