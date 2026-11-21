"""Agregações fixas por caso; sem target, ajuste global ou escolha por rótulo."""
import csv
from pathlib import Path
import yaml
from pyspark.sql import functions as F,Window

META={'case_id':'bigint','date_decision':'date','MONTH':'bigint','WEEK_NUM':'bigint'}


def prefix(table):return table.removeprefix('train_')+'__'


def load_features(path,contract):
    config=yaml.safe_load(Path(path).read_text())
    if (config['version']!=1 or config['scope']!='retrospective_features_no_fitted_preprocessing'
            or config['predictor_availability']!='unproven_no_point_in_time_allowlist'
            or config['missing_history']!='zero_counts_false_flags_null_values'
            or config['numeric_aggregates']!=['non_null_count','mean','max']):
        raise ValueError('Política de atributos não suportada')
    if set(config['sources'])!=set(contract['tables'])-{'train_base'}:raise ValueError('Fontes incompletas')
    for name,rule in config['sources'].items():
        spec=contract['tables'][name]
        cols=rule.get('columns',[])+rule.get('numeric',[])+rule.get('dates',[])+rule.get('categories',[])
        if (not set(cols)<=set(spec['schema']) or set(cols)&set(spec['key'])
                or any(c.startswith('_') or c in {'target','MONTH','WEEK_NUM','date_decision'} for c in cols)):
            raise ValueError('Coluna de atributo inválida ou vazamento técnico/rótulo')
        if rule['kind']=='direct' and len(spec['key'])!=1:raise ValueError('Fonte direta não é 1:1')
        if rule['kind']=='applicant' and 'num_group1' not in spec['key']:raise ValueError('Solicitante sem índice')
        if any(spec['schema'][c] not in ('double','float','bigint','int') for c in rule.get('numeric',[])):raise ValueError('Agregado numérico inválido')
        if any(spec['schema'][c]!='date' for c in rule.get('dates',[])):raise ValueError('Data não tipada')
        if any(spec['schema'][c]!='string' for c in rule.get('categories',[])):raise ValueError('Categoria não textual')
    return config


def block_schema(table,rule,spec):
    p=prefix(table);schema={'case_id':'bigint',p+'has_source':'boolean',p+'observation_count':'bigint'}
    if 'num_group2' in spec['key']:schema[p+'group_count']='bigint'
    if rule['kind']=='applicant':schema[p+'has_applicant']='boolean'
    for c in rule.get('columns',[]):schema[p+c]=spec['schema'][c]
    for c in rule.get('numeric',[]):
        schema[p+c+'__non_null_count']='bigint';schema[p+c+'__mean']='double';schema[p+c+'__max']=spec['schema'][c]
    for c in rule.get('dates',[]):schema[p+c+'__min']='date';schema[p+c+'__max']='date'
    for c in rule.get('categories',[]):schema[p+c+'__mode']='string'
    return schema


def mode_block(frame,column,name):
    window=Window.partitionBy('case_id').orderBy(F.desc('__frequency'),F.asc(column))
    return (frame.where(F.col(column).isNotNull()).groupBy('case_id',column).count()
        .withColumnRenamed('count','__frequency').withColumn('__rank',F.row_number().over(window))
        .where('__rank=1').select('case_id',F.col(column).alias(name)))


def aggregate_block(frame,table,rule,spec):
    p=prefix(table)
    if rule['kind']=='direct':
        return frame.select('case_id',F.lit(True).alias(p+'has_source'),F.lit(1).cast('long').alias(p+'observation_count'),
                            *[F.col(c).alias(p+c) for c in rule['columns']])
    if rule['kind']=='applicant':
        agg=[F.count('*').alias(p+'observation_count'),F.max(F.col('num_group1')==0).alias(p+'has_applicant')]
        agg += [F.max(F.when(F.col('num_group1')==0,F.col(c))).alias(p+c) for c in rule['columns']]
        return frame.groupBy('case_id').agg(*agg).withColumn(p+'has_source',F.lit(True))
    numeric=rule.get('numeric',[]);dates=rule.get('dates',[])
    nested='num_group2' in spec['key']
    if nested:
        # Dois níveis explícitos; médias ponderadas pelas contagens, nunca média de médias.
        groups=frame.groupBy('case_id','num_group1').agg(F.count('*').alias('__rows'),
            *[expr for c in numeric for expr in [F.count(c).alias(c+'__n'),F.sum(c).alias(c+'__s'),F.max(c).alias(c+'__x')]],
            *[expr for c in dates for expr in [F.min(c).alias(c+'__lo'),F.max(c).alias(c+'__hi')]])
        expressions=[F.sum('__rows').alias(p+'observation_count'),F.count('*').alias(p+'group_count')]
        for c in numeric:
            expressions += [F.sum(c+'__n').alias(p+c+'__non_null_count'),
                F.when(F.sum(c+'__n')>0,F.sum(c+'__s')/F.sum(c+'__n')).alias(p+c+'__mean'),F.max(c+'__x').alias(p+c+'__max')]
        for c in dates:expressions += [F.min(c+'__lo').alias(p+c+'__min'),F.max(c+'__hi').alias(p+c+'__max')]
        result=groups.groupBy('case_id').agg(*expressions)
    else:
        expressions=[F.count('*').alias(p+'observation_count')]
        for c in numeric:expressions += [F.count(c).alias(p+c+'__non_null_count'),F.avg(c).alias(p+c+'__mean'),F.max(c).alias(p+c+'__max')]
        for c in dates:expressions += [F.min(c).alias(p+c+'__min'),F.max(c).alias(p+c+'__max')]
        result=frame.groupBy('case_id').agg(*expressions)
    for c in rule.get('categories',[]):result=result.join(mode_block(frame,c,p+c+'__mode'),'case_id','left')
    return result.withColumn(p+'has_source',F.lit(True)).select(*block_schema(table,rule,spec))


def sql_oracle(spark,frame,table,rule,spec):
    """SQL direto por caso, independente da agregação hierárquica do builder."""
    view='oracle_'+table;frame.createOrReplaceTempView(view);p=prefix(table)
    if rule['kind']=='direct':
        cols=', '.join(f'`{c}` AS `{p+c}`' for c in rule['columns'])
        return spark.sql(f'SELECT case_id, TRUE AS `{p}has_source`, CAST(1 AS BIGINT) AS `{p}observation_count`, {cols} FROM {view}')
    expr=[f'COUNT(*) AS `{p}observation_count`']
    if rule['kind']=='applicant':
        expr += [f'MAX(num_group1=0) AS `{p}has_applicant`']
        expr += [f'MAX(CASE WHEN num_group1=0 THEN `{c}` END) AS `{p+c}`' for c in rule['columns']]
    else:
        if 'num_group2' in spec['key']:expr += [f'COUNT(DISTINCT num_group1) AS `{p}group_count`']
        for c in rule.get('numeric',[]):expr += [f'COUNT(`{c}`) AS `{p+c}__non_null_count`',f'AVG(`{c}`) AS `{p+c}__mean`',f'MAX(`{c}`) AS `{p+c}__max`']
        for c in rule.get('dates',[]):expr += [f'MIN(`{c}`) AS `{p+c}__min`',f'MAX(`{c}`) AS `{p+c}__max`']
    result=spark.sql(f'SELECT case_id, TRUE AS `{p}has_source`, '+', '.join(expr)+f' FROM {view} GROUP BY case_id')
    for c in rule.get('categories',[]):
        mode=spark.sql(f'''SELECT case_id, `{c}` AS `{p+c}__mode` FROM (
            SELECT case_id, `{c}`, ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY COUNT(*) DESC, `{c}` ASC) AS r
            FROM {view} WHERE `{c}` IS NOT NULL GROUP BY case_id, `{c}`) WHERE r=1''')
        result=result.join(mode,'case_id','left')
    return result.select(*block_schema(table,rule,spec))


def feature_catalog(config,contract,definitions):
    entries=[]
    for table,rule in config['sources'].items():
        p=prefix(table)
        for name,typ in block_schema(table,rule,contract['tables'][table]).items():
            if name=='case_id':continue
            tail=name[len(p):]
            source=tail.split('__')[0] if tail.split('__')[0] in contract['tables'][table]['schema'] else None
            operation=tail[len(source)+2:] if source and '__' in tail else ('direct_applicant_index_zero' if rule['kind']=='applicant' and source else 'direct' if source else tail)
            null_policy='zero_count_or_false_flag_when_no_source' if tail.endswith(('_count','has_source','has_applicant')) else 'preserve_null_if_missing_or_all_null'
            entries.append({'name':name,'type':typ,'source_table':table,'source_column':source,
                'aggregation':operation,'description':definitions.get(source,'Structural observation/coverage count; not a count of unique loans or clients.'),
                'unit':('observation_count' if operation=='non_null_count' or tail.endswith('_count') else
                        'boolean' if typ=='boolean' else 'transformed_calendar_date' if typ=='date' else
                        'coded_category' if typ=='string' else 'transformed_amount_no_currency_proof' if source and source.endswith('A') else
                        'transformed_dpd' if source and source.endswith('P') else 'source_numeric_units'),
                'null_policy':null_policy,'temporal_status':'retrospective_availability_unproven',
                'ml_eligible':False,'reason':'no_historical_available_at_evidence'})
    return {'version':1,'scope':'retrospective_abt','grain':'one_row_per_case_id',
        'metadata':META,'label_schema':{'case_id':'bigint','target':'bigint'},'features':entries,
        'eligible_predictors':[],'ml_ready':False,'label_maturation':'horizon_and_available_at_not_disclosed',
        'client_identity':'case_id_is_credit_case_not_proven_person_identifier',
        'evaluation_labels':'separate_delta_path_opt_in_reader',
        'preprocessing':'no_fitted_statistics_or_vocabulary','float_tolerance':config['float_comparison']}
