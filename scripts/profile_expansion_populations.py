"""Contagens exatas das populações E00, sem alterar RAW ou o perfil Spark."""
import json
from pathlib import Path
from datetime import datetime, timezone
from pyspark.sql import functions as F
from src.utils.paths import load_paths
from src.utils.spark import create_spark_session

root = Path(__file__).resolve().parents[1]
spark = create_spark_session(root, app_name='credit-risk-expansion-e00')
try:
    raw = load_paths(root)['raw_dir']
    base = spark.read.parquet(str(raw / 'parquet_files/train/train_base.parquet'))
    base = base.withColumn('_decision', F.to_date('date_decision')).cache()
    def stats(frame):
        return frame.agg(F.count('*').alias('cases'),
            F.countDistinct('case_id').alias('distinct_cases'),
            F.min('_decision').alias('min_date'), F.max('_decision').alias('max_date'),
            F.sum(F.when(F.col('target') == 1, 1).otherwise(0)).alias('target_1'),
            F.sum(F.when(F.col('target') == 0, 1).otherwise(0)).alias('target_0'),
            F.sum(F.when(F.col('target').isNull() | ~F.col('target').isin(0,1), 1).otherwise(0)).alias('invalid_target')
        ).first().asDict()
    windows = {'development': ('2020-01-01','2020-06-01'),
               'evaluation': ('2020-06-01','2020-10-01'),
               'public': ('2020-01-01','2020-10-01')}
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': 'parquet_files/train/train_base.parquet',
              'full_base': stats(base), 'windows': {}}
    for name, (start,end) in windows.items():
        frame = base.filter((F.col('_decision') >= F.lit(start).cast('date')) &
                            (F.col('_decision') < F.lit(end).cast('date')))
        report['windows'][name] = {'start_inclusive': start, 'end_exclusive': end,
            **stats(frame), 'monthly': [r.asDict() for r in frame.groupBy(
                F.date_format('_decision','yyyy-MM').alias('month')).agg(
                F.count('*').alias('cases'), F.sum('target').alias('target_1')).orderBy('month').collect()]}
    assert report['windows']['development']['cases'] + report['windows']['evaluation']['cases'] == report['windows']['public']['cases']
    out = root / 'artifacts/expansion/populations.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,default=str)+'\n')
    print(json.dumps(report,indent=2,default=str))
finally:
    spark.stop()
