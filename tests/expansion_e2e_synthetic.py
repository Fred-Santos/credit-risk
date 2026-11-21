"""E08: RAW inventada → Bronze temporal → Silver → ABTs → análise → S3."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'.runtime/analysis')]
import csv,json,os,shutil,tempfile,uuid,yaml
from pyspark.sql import functions as F
from src.bronze.expansion import build_temporal_bronze,load_temporal_policy,METADATA
from src.expansion.silver import build_silver
from src.expansion.features import load_features,feature_catalog
from src.expansion.temporal import audit_temporal
from src.expansion.gold import build_gold,open_abt,open_ml_inputs
from src.expansion.analysis import build_analysis
from src.expansion.publication import publish,consume
from src.object_store.client import ObjectClient
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.pipelines.download_home_credit import download_selected,sha256


def run():
    for key in list(os.environ):
        if key.startswith(('KAGGLE_','AWS_')):os.environ.pop(key)
    os.environ['MPLCONFIGDIR']=str(ROOT/'.runtime/analysis-mpl')
    service=ObjectService(ROOT);preexisting=service.status()['status']=='running';service.start()
    spark=create_object_spark(ROOT,app_name='expansion-raw-to-s3-e2e')
    client=ObjectClient(ROOT);client.config={**client.config,'prefix':'fixtures/expansion-e2e/'+uuid.uuid4().hex}
    prefix=client.config['prefix']
    try:
        with tempfile.TemporaryDirectory(prefix='credit-risk-expansion-e2e-') as tmp:
            repo=Path(tmp);(repo/'configs/contracts').mkdir(parents=True)
            frames={
                'train_base':spark.createDataFrame([(1,'2019-12-31',201912,51,0),(2,'2020-01-01',202001,52,1),(3,'2020-05-31',202005,74,0),(4,'2020-06-01',202006,75,1),(5,'2020-09-30',202009,91,0),(6,'2020-10-01',202010,92,1)],
                    'case_id long,date_decision string,MONTH long,WEEK_NUM long,target long'),
                'train_static_0':spark.createDataFrame([(i,value,code) for i,value,code in [(1,1.,'A'),(2,100.,'A'),(3,200.,'B'),(4,None,'A'),(5,0.,None),(6,1.,'A')]],'case_id long,annuity_780A double,credtype_322L string'),
                'train_applprev_1':spark.createDataFrame([(1,0,1.,'2019-01-01','A'),(2,0,10.,'2018-01-01','A'),(2,1,None,'2021-01-01','B'),(4,0,0.,'2019-01-01','A'),(5,0,None,None,None)],'case_id long,num_group1 long,credamount_590A double,creationdate_885D string,status_219L string'),
                'train_applprev_2':spark.createDataFrame([(2,0,0,'active'),(2,0,1,'blocked'),(4,0,0,None)],'case_id long,num_group1 long,num_group2 long,credacc_cards_status_52L string'),
                'train_person_1':spark.createDataFrame([(2,0,100.,'A'),(2,1,1000.,'B'),(3,1,900.,'B'),(4,0,0.,'A')],'case_id long,num_group1 long,mainoccupationinc_384A double,education_927M string')}
            catalog={'dictionary':'feature_definitions.csv','tables':{}};payload={}
            for name,frame in frames.items():
                path=repo/'fixture_parquets'/name;frame.coalesce(1).write.parquet(str(path));part=next(path.glob('*.parquet'))
                filename=name+('_0' if name in ('train_static_0','train_applprev_1') else '')+'.parquet'
                remote='parquet_files/train/'+filename;payload[remote]=part;catalog['tables'][name]=[{'name':remote,'bytes':part.stat().st_size}]
            dictionary=repo/'fixture_dictionary.csv';dictionary.write_text('Variable,Description\nfixture,Invented data only\n');payload[catalog['dictionary']]=dictionary
            def fetch(remote,stage):
                dest=stage/remote;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(payload[remote],dest)
            download_selected(repo/'data/raw',files=list(payload),fetch=fetch)
            policy=load_temporal_policy(ROOT/'configs/temporal_policy_v1.yaml')
            (repo/'configs/temporal_policy_v1.yaml').write_text(yaml.safe_dump(policy))
            bm,reused=build_temporal_bronze(repo,spark,catalog,policy)
            bronze=repo/'data/bronze/expansion'/bm['selection_id'];assert bm['population']['selected_cases']==4
            contract={'version':1,'scope':'expansion_silver_retrospective','failure_policy':'block_entire_snapshot_preserve_input','date_policy':'strict_iso_roundtrip_zero_loss','future_dates':'preserve_not_availability_evidence','tables':{}}
            for name,frame in frames.items():
                schema={**dict(frame.dtypes),**{c:'string' for c in METADATA}}
                dates=[c for c in schema if c.endswith('D') or c=='date_decision'];key=[c for c in ('case_id','num_group1','num_group2') if c in schema]
                output={c:'date' if c in dates else t for c,t in schema.items()};output.update(_source_revision='bigint',_is_simulated='boolean')
                contract['tables'][name]={'source_table':name,'input_schema':schema,'schema':output,'date_columns':dates,'key':key,
                    'group_parent':'train_applprev_1' if name=='train_applprev_2' else None,'required_base_coverage':name=='train_static_0'}
            cp=repo/'configs/contracts/expansion_silver_v1.yaml';cp.write_text(yaml.safe_dump(contract))
            sm,_=build_silver(repo,spark,bronze,cp);silver=repo/'data/silver/expansion'/sm['id']
            cfg=yaml.safe_load((ROOT/'configs/expansion_features_v1.yaml').read_text());cfg['sources']={
                'train_static_0':{'kind':'direct','columns':['annuity_780A','credtype_322L']},
                'train_applprev_1':{'kind':'history','numeric':['credamount_590A'],'dates':['creationdate_885D'],'categories':['status_219L']},
                'train_applprev_2':{'kind':'history','numeric':[],'dates':[],'categories':['credacc_cards_status_52L']},
                'train_person_1':{'kind':'applicant','columns':['mainoccupationinc_384A','education_927M']}}
            fp=repo/'configs/expansion_features_v1.yaml';fp.write_text(yaml.safe_dump(cfg))
            gc=feature_catalog(cfg,contract,{});gc.update(silver_contract_sha256=sha256(cp),feature_policy_sha256=sha256(fp),dictionary_sha256=sha256(repo/'data/raw/feature_definitions.csv'))
            gp=repo/'configs/contracts/expansion_gold_v1.yaml';gp.write_text(yaml.safe_dump(gc))
            audit_path=repo/'artifacts/expansion/temporal'/(sm['id']+'.json');audit=audit_temporal(repo,spark,silver,cp,output=audit_path)
            assert audit['date_ranges']['train_applprev_1']['creationdate_885D']['after_decision']==1
            gm,_=build_gold(repo,spark,silver,cp,fp,gp,policy,audit_path=audit_path);gold=repo/'data/gold/expansion'/gm['id']
            dev=open_abt(repo,spark,gold,'development');eva=open_abt(repo,spark,gold,'evaluation')
            assert dev.count()==eva.count()==2 and dev.join(eva,'case_id').count()==0
            assert dev.where('case_id=2').first()['person_1__mainoccupationinc_384A']==100.
            assert dev.where('case_id=3').first()['applprev_1__observation_count']==0
            assert eva.where('case_id=5').first()['applprev_1__credamount_590A__mean'] is None
            assert eva.where('case_id=4').first()['applprev_1__credamount_590A__mean']==0.0
            assert str(dev.where('case_id=2').first()['applprev_1__creationdate_885D__max'])=='2021-01-01'
            try:open_ml_inputs(repo,spark,gold,'development')
            except ValueError:pass
            else:raise AssertionError('Fixture sem evidência temporal liberou treino')
            ap=yaml.safe_load((ROOT/'configs/expansion_analysis_v1.yaml').read_text());ap['selected_numeric']=['static_0__annuity_780A'];ap['categories']={'product_code':'static_0__credtype_322L','education_code':'person_1__education_927M'}
            pp=repo/'configs/expansion_analysis_v1.yaml';pp.write_text(yaml.safe_dump(ap))
            am,_=build_analysis(repo,spark,silver,gold,pp);analysis=repo/'data/gold/expansion-analysis'/am['id']
            publication,attempt=publish(repo,client,spark,silver,gold,analysis)
            manifest,remote=consume(client,spark,bm['selection_id'])
            assert len(manifest['tables'])==18 and 'gold.evaluation_labels' not in remote
            assert 'target' not in remote['silver.train_base'].columns
            assert remote['gold.development_features'].count()==remote['gold.evaluation_features'].count()==2
            assert remote['gold.analysis_monthly'].count()==9
            result={'status':'passed','data_kind':'synthetic_fixture_only','raw_to_expansion_s3':True,
                'kaggle_access':False,'tables':18,'cases':4,'source_tables':5,'ml_ready':False,
                'levels':[0,1,2],'boundaries_and_missing_auxiliaries':True,'labels_separated':True}
    finally:
        spark.stop()
        for key in client.list(prefix+'/'):client.s3.delete_object(Bucket=client.bucket,Key=key)
        if not preexisting:service.stop()
    result['temporary_lab_removed']=not repo.exists()
    return result


if __name__=='__main__':
    result=run();target=ROOT/'artifacts/expansion/e08/expansion_e2e.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n');print('expansion_e2e_passed '+json.dumps(result))
