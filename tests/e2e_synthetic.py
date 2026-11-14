"""RAW sintética → recorte → Bronze → replay F04 → publicação S3 F09, sem Kaggle."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import importlib.util
import json
import os
import shutil
import tempfile
from unittest.mock import patch
import yaml
from src.utils.run_context import RunContext
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.object_store.client import ObjectClient
from src.object_store.publication import verify_publication,current
from src.pipelines.download_home_credit import sha256
from src.pipelines.build_sample import build_sample
from src.bronze.inputs import bind_sample
from src.pipelines.run_bronze_mvp import run_bronze
from src.pipelines import run_incremental_demo as incremental
from src.operation.runner import supervise

spec=importlib.util.spec_from_file_location('fixture_source_export',ROOT/'scripts/export_source.py')
exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)


def write_yaml(path,value):path.write_text(yaml.safe_dump(value,sort_keys=False))


def run():
    for key in list(os.environ):
        if key.startswith(('KAGGLE_','AWS_')):os.environ.pop(key)
    with tempfile.TemporaryDirectory(prefix='credit-risk-synthetic-') as folder:
        repo=Path(folder)/'source';exporter.export(repo)
        assert not (repo/'data').exists() and not (repo/'.kaggle').exists()
        runtime=repo/'.runtime';runtime.mkdir()
        (ROOT/'.runtime/ivy').mkdir(parents=True,exist_ok=True)
        (runtime/'ivy').symlink_to(ROOT/'.runtime/ivy',target_is_directory=True)
        binary=runtime/'object-store/bin';binary.mkdir(parents=True)
        (binary/'weed').symlink_to(ROOT/'.runtime/object-store/bin/weed')
        cfg=yaml.safe_load((repo/'configs/object_store_v1.yaml').read_text())
        for key,port in [('master_port',32150),('volume_port',32151),('filer_port',32152),('s3_port',32153),('admin_port',32154)]:cfg[key]=port
        cfg['endpoint']='http://127.0.0.1:32153';write_yaml(repo/'configs/object_store_v1.yaml',cfg)
        service=ObjectService(repo);service.start();spark=None
        try:
            spark=create_object_spark(repo,app_name='synthetic-source')
            tables={
                'train_base': ([(1,'2019-01-01',201901,0,0),(2,'2019-01-02',201901,1,1),
                                (3,'2020-01-01',202001,52,0),(4,'2020-07-01',202007,78,1)],
                               'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long'),
                'train_static_0': ([(1,10.),(2,20.),(3,None),(4,40.)],'case_id long, annuity_780A double'),
                'train_applprev_1': ([(1,0,5.,'2018-12-01'),(1,1,None,None),(2,0,7.,'2018-12-02'),(3,0,None,None)],
                                    'case_id long, num_group1 long, credamount_590A double, observedD string')}
            contract={'version':1,'scope':'synthetic_fixture_only','source':'synthetic_fixture_only','sources':{},'tables':{}}
            raw=repo/'data/raw';(raw/'parquet_files/train').mkdir(parents=True)
            csv=raw/'feature_definitions.csv';csv.write_text('Variable,Description\nfixture,Invented data only\n')
            for name,(rows,schema) in tables.items():
                frame=spark.createDataFrame(rows,schema)
                filename='parquet_files/train/'+name+('' if name=='train_base' else '_0')+'.parquet'
                staging=repo/'staging'/name;frame.coalesce(1).write.parquet(str(staging))
                shutil.copyfile(next(staging.glob('part-*.parquet')),raw/filename)
                key=['case_id','num_group1'] if name=='train_applprev_1' else ['case_id']
                table={'schema':dict(frame.dtypes),'key':key,'required_non_null':list(frame.columns) if name=='train_base' else key,
                    'minimum_rows':0 if name=='train_applprev_1' else 1,'grain':'synthetic_fixture','files':[filename]}
                if name!='train_base':table['reference']={'table':'train_base','columns':['case_id'],'full_coverage':name=='train_static_0'}
                contract['tables'][name]=table
            for path in [csv,*sorted((raw/'parquet_files/train').glob('*.parquet'))]:
                contract['sources'][path.relative_to(raw).as_posix()]={'sha256':sha256(path),'bytes':path.stat().st_size}
            source=repo/'configs/contracts/home_credit_v1.yaml';write_yaml(source,contract)
            policy_path=repo/'configs/sample_policy.yaml';policy=yaml.safe_load(policy_path.read_text());policy['max_cases']=4;write_yaml(policy_path,policy)
            silver_path=repo/'configs/silver_policy_v1.yaml';silver=yaml.safe_load(silver_path.read_text());silver['snapshot_contract_sha256']=sha256(source)
            silver['tables']={n:{'key':contract['tables'][n]['key'],'cast_to_date':[c for c in contract['tables'][n]['schema'] if c=='date_decision' or c.endswith('D')]} for n in tables}
            write_yaml(silver_path,silver)
            for relative,fields in [
                ('configs/contracts/home_credit_events_v1.yaml',{'snapshot_contract_sha256':sha256(source)}),
                ('configs/contracts/silver_initial_v1.yaml',{'snapshot_contract_sha256':sha256(source),'silver_policy_sha256':sha256(silver_path)})]:
                path=repo/relative;doc=yaml.safe_load(path.read_text());doc.update(fields);write_yaml(path,doc)
            path=repo/'configs/contracts/silver_managed_v2.yaml';doc=yaml.safe_load(path.read_text());doc['parent_contract_sha256']=sha256(repo/'configs/contracts/silver_initial_v1.yaml');write_yaml(path,doc)
            path=repo/'configs/contracts/gold_v1.yaml';doc=yaml.safe_load(path.read_text());doc['silver_contract_sha256']=sha256(repo/'configs/contracts/silver_managed_v2.yaml');write_yaml(path,doc)
            sample=build_sample(RunContext.create(repo),spark,source,policy_path)
            selection=sample['selection_id'];bronze=run_bronze(bind_sample(RunContext.create(repo),selection),spark)
            assert bronze['status']=='passed'
            publish=incremental.publish_packet
            def fixture_packet(*args,**kwargs):
                from pyspark.sql import functions as F
                kwargs['frames']={n:f.withColumn('_payload_origin',F.when(F.col('_scenario')=='correction_simulation',F.col('_payload_origin')).otherwise(F.lit('synthetic_fixture'))) for n,f in kwargs['frames'].items()}
                return publish(*args,**kwargs)
            with patch.object(incremental,'publish_packet',fixture_packet):f04=incremental.run_incremental_demo(RunContext.create(repo),spark,selection)
            spark.stop();spark=None
            operation=supervise(repo,{'sample':selection,'source_report':str(Path(f04['report']).relative_to(repo)),
                'mode':'replay','batch':None},max_attempts=1)
            assert operation['exit_code']==0
            op=json.loads(Path(operation['report']).read_text());run_report=json.loads(Path(op['result']['report']).read_text())
            spark=create_object_spark(repo,app_name='synthetic-oracle');client=ObjectClient(repo)
            manifest,frames=verify_publication(client,run_report['registry'],run_report['publication_id'],spark)
            abt={r.case_id:r.asDict() for r in frames['gold.abt'].collect()}
            assert set(abt)=={1,2,3,4} and abt[1]['static_annuity']==11 and abt[1]['previous_amount_sum']==6
            assert abt[2]['previous_amount_sum']==7 and abt[3]['previous_amount_sum'] is None and abt[3]['has_previous_applications']
            assert abt[3]['has_static'] and abt[3]['static_annuity'] is None
            assert abt[4]['previous_application_count']==0 and not abt[4]['has_previous_applications']
            months={r.MONTH:r.asDict() for r in frames['gold.monthly_metrics'].collect()}
            assert {m:(r['case_count'],r['target_1_count']) for m,r in months.items()}=={201901:(2,1),202001:(1,0),202007:(1,1)}
            assert run_report['counts']=={'credit_cases':4,'credit_static':4,'previous_applications':4}
            result={'status':'passed','data_kind':'synthetic_fixture_only','raw_to_published_s3':True,
                'stages':['raw','sample','bronze','incremental_f04','operational_s3','gold','independent_hand_oracle'],
                'cases':4,'history_rows':4,'months':3,'kaggle_access':False,'notebook_outputs':0}
        finally:
            if spark is not None:spark.stop()
            service.stop()
    assert not repo.exists()
    result['temporary_lab_removed']=True
    return result


if __name__=='__main__':
    result=run();target=ROOT/'artifacts/tests/e2e_result.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n');print('synthetic_e2e_passed '+json.dumps(result))
