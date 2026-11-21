"""Snapshots inventados, pequenos e coerentes para E06/E07."""
from pathlib import Path
import json
import yaml
from pyspark.sql import functions as F
from src.expansion.storage import digest,pin_delta,finish_package
from src.pipelines.download_home_credit import sha256


def fixture(repo,spark,variant=0):
    (repo/'configs/contracts').mkdir(parents=True)
    base=spark.createDataFrame([(1,'2020-01-01',202001,1,0),(2,'2020-01-31',202001,5,1),(3,'2020-06-01',202006,23,0)],
        'case_id long,date_decision string,MONTH long,WEEK_NUM long,target long').withColumn('date_decision',F.to_date('date_decision'))
    aux=spark.createDataFrame([(1,0,10.0+variant),(1,1,20.0),(3,0,None)],'case_id long,num_group1 long,amount double')
    contract={'version':1,'scope':'expansion_silver_retrospective','failure_policy':'block_entire_snapshot_preserve_input',
        'date_policy':'strict_iso_roundtrip_zero_loss','future_dates':'preserve_not_availability_evidence','tables':{}}
    for name,frame,key in [('train_base',base,['case_id']),('train_applprev_1',aux,['case_id','num_group1'])]:
        schema=dict(frame.dtypes);contract['tables'][name]={'source_table':name,'key':key,'input_schema':schema,'schema':{**schema,'_source_revision':'bigint','_is_simulated':'boolean'},'date_columns':[]}
    (repo/'configs/contracts/expansion_silver_v1.yaml').write_text(yaml.safe_dump(contract))
    identity={'scope':'invented_delivery_fixture','bronze_selection_id':'a'*24,'variant':variant};sid=digest(identity)[:24]
    silver=repo/'data/silver/expansion'/sid;stage=silver.parent/'.staging/silver';stage.mkdir(parents=True)
    sm={'id':sid,'identity':identity,'identity_sha256':digest(identity),'status':'running','tables':{},'is_simulated':bool(variant)}
    for name,frame in [('train_base',base),('train_applprev_1',aux)]:
        path=stage/'tables'/name;frame.write.format('delta').save(str(path));sm['tables'][name]=pin_delta(spark,path,str((silver/'tables'/name).relative_to(repo)),frame.count())
    sm=finish_package(stage,silver,sm,'_silver.json')
    block=aux.groupBy('case_id').agg(F.count('*').alias('applprev_1__observation_count'),F.avg('amount').alias('amount_mean')).withColumn('applprev_1__has_source',F.lit(True))
    features=base.drop('target').join(block,'case_id','left').fillna({'applprev_1__observation_count':0,'applprev_1__has_source':False})\
        .withColumn('product_code',F.when(F.col('case_id')==1,F.lit('__NULL__')).when(F.col('case_id')==2,F.lit(None).cast('string')).otherwise('regular'))
    identity={'scope':'invented_delivery_gold','silver_manifest_sha256':sha256(silver/'_silver.json'),'silver_id':sid};gid=digest(identity)[:24]
    gold=repo/'data/gold/expansion'/gid;stage=gold.parent/'.staging/gold';stage.mkdir(parents=True)
    gm={'id':gid,'identity':identity,'identity_sha256':digest(identity),'status':'running','dependencies':sm['tables'],
        'blocks':{},'products':{},'case_intersection':0,'ml_ready':False,'eligible_predictors':[]}
    path=stage/'blocks/train_applprev_1';block.write.format('delta').save(str(path))
    gm['blocks']['train_applprev_1']=pin_delta(spark,path,str((gold/'blocks/train_applprev_1').relative_to(repo)),block.count())
    for name,predicate in [('development',"date_decision < DATE '2020-06-01'"),('evaluation',"date_decision >= DATE '2020-06-01'")]:
        gm['products'][name]={}
        for kind,frame in [('features',features.where(predicate)),('labels',base.where(predicate).select('case_id','target'))]:
            path=stage/'products'/name/kind;frame.write.format('delta').save(str(path))
            gm['products'][name][kind]=pin_delta(spark,path,str((gold/'products'/name/kind).relative_to(repo)),frame.count())
    finish_package(stage,gold,gm,'_gold.json')
    policy={'version':1,'scope':'retrospective_full_public_population','start_inclusive':'2020-01-01','end_exclusive':'2020-10-01',
        'small_group_min_cases':500,'small_group_min_target_1':20,'labels':'explicit_descriptive_access_no_model_selection',
        'history_source':'applprev_1__observation_count','categories':{'product_code':'product_code'},'selected_numeric':['amount_mean'],
        'amount_units':'transformed_no_currency_claim','causal_or_operational_default_claim':'forbidden','reserve_use':'descriptive_only_no_fitted_preprocessing'}
    policy_path=repo/'configs/expansion_analysis_v1.yaml';policy_path.write_text(yaml.safe_dump(policy))
    return silver,gold,policy_path
