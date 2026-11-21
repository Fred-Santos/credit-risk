"""Auditoria exata por chave única; evita agrupar linhas largas inteiras."""
from functools import reduce
from pyspark.sql import functions as F


def check_schema(frame,schema):
    if dict(frame.dtypes)!=schema or len(frame.columns)!=len(schema):
        raise ValueError('Schema fora do contrato; casts implícitos proibidos')


def key_audit(frame,key):
    nulls=frame.where(reduce(lambda a,b:a|b,[F.col(c).isNull() for c in key])).limit(1).count()
    groups=frame.groupBy(*key).count().agg(
        F.coalesce(F.sum('count'),F.lit(0)).alias('rows'),
        F.count('*').alias('distinct_keys'),
        F.coalesce(F.sum(F.when(F.col('count')>1,1).otherwise(0)),F.lit(0)).alias('duplicate_groups')).first().asDict()
    groups['null_keys_observed']=bool(nulls)
    if nulls or groups['duplicate_groups']:
        raise ValueError('Chave nula ou duplicada; publicação bloqueada')
    return groups


def compare_keyed(expected,actual,key,*,numeric_tolerance=None):
    """Caller audita unicidade/nulos nas duas entradas; join compara cada célula."""
    check_schema(actual,dict(expected.dtypes))
    columns=[c for c in expected.columns if c not in key]
    left=expected.withColumn('__left_present',F.lit(True)).alias('l')
    right=actual.withColumn('__right_present',F.lit(True)).alias('r')
    joined=left.join(right,key,'full_outer')
    mismatch=F.lit(False)
    for c in columns:
        a,b=F.col('l.'+c),F.col('r.'+c)
        equal=a.eqNullSafe(b)
        if numeric_tolerance and dict(expected.dtypes)[c] in ('float','double'):
            absolute,relative=numeric_tolerance
            equal=equal | (a.isNotNull() & b.isNotNull() &
                (F.abs(a-b)<=F.lit(absolute)+F.lit(relative)*F.greatest(F.abs(a),F.abs(b))))
        mismatch=mismatch|~equal
    missing=F.col('__right_present').isNull()
    extra=F.col('__left_present').isNull()
    stats=joined.agg(*[F.coalesce(F.sum(cond.cast('long')),F.lit(0)).alias(name)
        for name,cond in [('missing_rows',missing),('extra_rows',extra),
                         ('changed_rows',~missing & ~extra & mismatch)]]).first().asDict()
    return {'success':not any(stats.values()),**stats,'method':'unique_key_full_outer_cell_comparison'}


def validate_silver(frame,spec,base_keys=None):
    check_schema(frame,spec['schema'])
    audit=key_audit(frame,spec['key'])
    bad=F.lit(False)
    for key in spec['key']:bad=bad | (F.col(key)<0)
    for c,t in spec['schema'].items():
        if t in ('float','double'):bad=bad | F.isnan(c) | (F.abs(F.col(c))==float('inf'))
    bad=bad | F.col('_source_file').isNull() | F.col('_selection_id').isNull() | F.col('_run_id').isNull() | F.col('_ingested_at_utc').isNull()
    bad=bad | F.col('_source_revision').isNull() | (F.col('_source_revision')<1) | F.col('_is_simulated').isNull()
    if 'target' in frame.columns:
        bad=bad | F.col('target').isNull() | ~F.col('target').isin(0,1) | F.col('date_decision').isNull()
        bad=bad | (F.col('MONTH')!=F.date_format('date_decision','yyyyMM').cast('long')) | F.col('MONTH').isNull() | F.col('WEEK_NUM').isNull() | (F.col('WEEK_NUM')<0)
    if frame.where(bad).limit(1).count():
        raise ValueError('Domínio/finito/proveniência inválidos; registros preservados na entrada')
    if base_keys is not None:
        orphans=frame.select('case_id').distinct().join(base_keys,'case_id','left_anti').count()
        if orphans:raise ValueError('Caso órfão')
        audit['orphan_cases']=orphans
    return audit
