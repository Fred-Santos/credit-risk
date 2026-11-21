"""Diagnóstico explícito de rejeições; registra fonte, chave e regra sem apagar entrada."""
import uuid
from pyspark.sql import functions as F
from src.expansion.quality import check_schema
from src.publication.protocol import atomic_json
from src.pipelines.download_home_credit import sha256


def diagnose(frame,spec,output,*,source_manifest_sha256):
    check_schema(frame,spec['input_schema'])
    reasons=[]
    for c in spec['key']:
        reasons.append(F.when(F.col(c).isNull() | (F.col(c)<0),F.lit('invalid_key:'+c)))
    for c in spec['date_columns']:
        parsed=F.try_to_timestamp(c,F.lit('yyyy-MM-dd')).cast('date')
        reasons.append(F.when(F.col(c).isNotNull() & (parsed.isNull() | (F.date_format(parsed,'yyyy-MM-dd')!=F.col(c))),F.lit('invalid_date:'+c)))
    for c,t in spec['input_schema'].items():
        if t in ('double','float'):reasons.append(F.when(F.isnan(c)|(F.abs(F.col(c))==float('inf')),F.lit('non_finite:'+c)))
    for c in ('_source_file','_selection_id','_run_id','_ingested_at_utc'):
        if c in frame.columns:reasons.append(F.when(F.col(c).isNull(),F.lit('missing_provenance:'+c)))
    if 'WEEK_NUM' in frame.columns:
        reasons.append(F.when(F.col('WEEK_NUM').isNull()|(F.col('WEEK_NUM')<0),F.lit('invalid_week')))
    duplicate=frame.groupBy(*spec['key']).count().where('count>1').select(*spec['key']).withColumn('__duplicate',F.lit(True))
    marked=frame.join(duplicate,spec['key'],'left')
    reasons.append(F.when(F.col('__duplicate'),F.lit('duplicate_key')))
    if 'target' in frame.columns:
        reasons.append(F.when(F.col('target').isNull()|~F.col('target').isin(0,1),F.lit('invalid_target')))
        reasons.append(F.when(F.col('MONTH').isNull()|(F.col('MONTH')!=F.date_format(F.to_date('date_decision'),'yyyyMM').cast('long')),F.lit('invalid_month')))
    rejected=marked.withColumn('_rejection_reasons',F.concat_ws('|',*reasons)).where("_rejection_reasons != ''").drop('__duplicate')
    count=rejected.count()
    if output.exists():raise FileExistsError('Diagnóstico anterior preservado')
    output.mkdir(parents=True)
    if count:rejected.write.parquet(str(output/'records'))
    report={'status':'rejected' if count else 'no_rejection_observed','rejected_rows':count,
        'source_manifest_sha256':source_manifest_sha256,'key':spec['key'],
        'records_path':'records' if count else None,'input_preserved':True}
    atomic_json(output/'report.json',report)
    return report
