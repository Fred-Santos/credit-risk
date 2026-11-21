"""E03–E05: Delta real, revisão auxiliar e ABTs em fixture inventada."""
import csv
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.utils.spark import create_spark_session
from src.expansion.silver import load_contract,open_silver
from src.expansion.storage import digest,pin_delta,finish_package,open_pin
from src.expansion.revisions import apply_revision
from src.expansion.features import load_features,feature_catalog
from src.expansion.temporal import audit_temporal
from src.expansion.gold import build_gold,open_abt,open_ml_inputs
from src.bronze.expansion import load_temporal_policy
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json
from pyspark.sql import functions as F


class ExpansionDeltaEndToEnd(unittest.TestCase):
    def test_revision_dependency_temporal_audit_and_two_abts(self):
        spark=create_spark_session(ROOT,app_name='expansion-fixture-delta',delta=True)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo=Path(tmp)
                contract=load_contract(ROOT/'configs/contracts/expansion_silver_v1.yaml')
                names=['train_base','train_static_0','train_other_1']
                contract['tables']={n:contract['tables'][n] for n in names}
                cp=repo/'silver.yaml';cp.write_text(yaml.safe_dump(contract))
                identity={'scope':'synthetic_fixture','invented':True};identifier=digest(identity)[:24]
                dest=repo/'data/silver/expansion'/identifier
                stage=dest.parent/'.staging/fixture';stage.mkdir(parents=True)
                population={'full_base_cases':2,'selected_cases':2,'outside_public_cases':0,'windows':{'development':1,'evaluation':1,'public':2}}
                manifest={'id':identifier,'identity':identity,'identity_sha256':digest(identity),'status':'running','tables':{},'population':population}
                for name in names:
                    schema=contract['tables'][name]['schema'];rows=[]
                    for case_id in (1,2):
                        decision=date(2020,5,31) if case_id==1 else date(2020,6,1)
                        values={}
                        for c,t in schema.items():
                            values[c]=10.0*case_id if t=='double' else 1 if t in ('bigint','int') else False if t=='boolean' else date(2019,1,1) if t=='date' else 'fixture'
                        values.update(case_id=case_id,_source_revision=1,_is_simulated=False,
                            _source_file='parquet_files/train/'+name+'.parquet',_selection_id='fixture',_run_id='fixture',_ingested_at_utc='2026-01-01T00:00:00Z')
                        if 'num_group1' in schema:values['num_group1']=0
                        if name=='train_base':values.update(date_decision=decision,MONTH=int(decision.strftime('%Y%m')),WEEK_NUM=case_id,target=case_id%2)
                        if name=='train_static_0' and case_id==1:values['lastapplicationdate_877D']=date(2021,1,1)
                        rows.append(tuple(values[c] for c in schema))
                    frame=spark.createDataFrame(rows,','.join(f'{c} {t}' for c,t in schema.items()))
                    path=stage/'tables'/name;frame.write.format('delta').save(str(path))
                    manifest['tables'][name]=pin_delta(spark,path,str((dest/'tables'/name).relative_to(repo)),2)
                parent=finish_package(stage,dest,manifest,'_silver.json')
                original_hash=sha256(dest/'_silver.json')
                _,frames=open_silver(repo,spark,dest)
                events=frames['train_other_1'].where('case_id=1').withColumn('amtdebitincoming_4809443A',F.col('amtdebitincoming_4809443A')+1)\
                    .withColumn('_source_revision',F.lit(2).cast('long')).withColumn('_is_simulated',F.lit(True))
                event_path=repo/'events';events.unionByName(events).write.parquet(str(event_path))
                ep=repo/'event.json';atomic_json(ep,{'is_simulated':True,'tables':{'train_other_1':{'path':'events',
                    'files':{p.name:sha256(p) for p in event_path.glob('*.parquet')}}}})
                child,reused=apply_revision(repo,spark,dest,cp,ep)
                self.assertFalse(reused);self.assertEqual(child['affected_cases']['rows'],1)
                self.assertEqual(child['affected_cases']['old_new_months'],[202005])
                self.assertEqual(child['changed_sources'],['train_other_1'])
                self.assertTrue(apply_revision(repo,spark,dest,cp,ep)[1])
                self.assertEqual(sha256(dest/'_silver.json'),original_hash)
                changed=open_pin(repo,spark,child['tables']['train_other_1'])
                self.assertEqual(changed.where('case_id=1').first()['amtdebitincoming_4809443A'],11.0)
                self.assertEqual(frames['train_other_1'].where('case_id=1').first()['amtdebitincoming_4809443A'],10.0)
                config=yaml.safe_load((ROOT/'configs/expansion_features_v1.yaml').read_text())
                config['sources']={n:r for n,r in config['sources'].items() if n in names}
                fp=repo/'features.yaml';fp.write_text(yaml.safe_dump(config))
                catalogue=feature_catalog(config,contract,{})
                catalogue.update(silver_contract_sha256=sha256(cp),feature_policy_sha256=sha256(fp),dictionary_sha256='synthetic')
                gp=repo/'gold.yaml';gp.write_text(yaml.safe_dump(catalogue))
                audit=repo/'audit.json';temporal=audit_temporal(repo,spark,dest,cp,output=audit)
                self.assertEqual(temporal['date_ranges']['train_static_0']['lastapplicationdate_877D']['after_decision'],1)
                self.assertFalse(temporal['ml_ready'])
                gold,reused=build_gold(repo,spark,dest,cp,fp,gp,load_temporal_policy(ROOT/'configs/temporal_policy_v1.yaml'),audit_path=audit)
                gold_path=repo/'data/gold/expansion'/gold['id']
                self.assertFalse(reused);self.assertEqual(gold['case_intersection'],0)
                dev=open_abt(repo,spark,gold_path,'development',include_labels=True)
                eva=open_abt(repo,spark,gold_path,'evaluation')
                self.assertEqual(dev.count(),1);self.assertEqual(eva.count(),1)
                self.assertNotIn('target',eva.columns)
                with self.assertRaises(PermissionError):open_abt(repo,spark,gold_path,'evaluation',include_labels=True)
                full=open_abt(repo,spark,gold_path,'evaluation',include_labels=True,allow_evaluation_labels=True)
                self.assertEqual(dev.dtypes,full.dtypes)
                with self.assertRaises(ValueError):open_ml_inputs(repo,spark,gold_path,'development')
                self.assertTrue(build_gold(repo,spark,dest,cp,fp,gp,load_temporal_policy(ROOT/'configs/temporal_policy_v1.yaml'),audit_path=audit)[1])
        finally:spark.stop()


if __name__=='__main__':unittest.main(verbosity=2)
