"""Auditoria temporal sem inferir available_at de uma data de evento."""
import json
from pathlib import Path
import time
from pyspark.sql import functions as F
from src.expansion.silver import open_silver,load_contract
from src.expansion.features import load_features,feature_catalog
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def audit_temporal(repo,spark,silver_path,contract_path,*,output):
    if output.exists():raise FileExistsError('Não sobrescrever auditoria temporal anterior')
    silver,frames=open_silver(repo,spark,silver_path)
    contract=load_contract(contract_path)
    base=frames['train_base'].select('case_id',F.col('date_decision').alias('__decision')).cache()
    report={'status':'running','silver_id':silver['id'],'silver_manifest_sha256':sha256(silver_path/'_silver.json'),
        'date_ranges':{},'availability_evidence':'absent_no_historical_available_at',
        'label_maturation':{'status':'unresolved','horizon_days':None,'label_available_at':None,
            'source':'https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data'},
        'client_overlap':{'status':'not_verifiable','reason':'case_id identifies credit case; group/person indices are local; masked employer codes are not client IDs'},
        'approved_point_in_time_predictors':[],'ml_ready':False}
    start=time.monotonic()
    try:
        for name,spec in contract['tables'].items():
            dates=[c for c in spec['date_columns'] if c!='date_decision']
            if not dates:continue
            frame=frames[name].select('case_id',*dates).join(base,'case_id','inner')
            expressions=[]
            for i,c in enumerate(dates):
                expressions += [F.count(c).alias(f'n{i}'),F.sum(F.when(F.col(c)>F.col('__decision'),1).otherwise(0)).alias(f'future{i}'),
                    F.min(c).alias(f'min{i}'),F.max(c).alias(f'max{i}')]
            values=frame.agg(*expressions).first().asDict()
            report['date_ranges'][name]={c:{'non_null':values[f'n{i}'],'after_decision':values[f'future{i}'],
                'min':str(values[f'min{i}']) if values[f'min{i}'] is not None else None,
                'max':str(values[f'max{i}']) if values[f'max{i}'] is not None else None,
                'interpretation':'future_date_is_flag_not_proof_of_leakage_or_availability'} for i,c in enumerate(dates)}
            print('Auditoria temporal:',name,flush=True)
        report.update(status='passed',duration_seconds=round(time.monotonic()-start,3))
        atomic_json(output,report)
        return report
    finally:base.unpersist()
