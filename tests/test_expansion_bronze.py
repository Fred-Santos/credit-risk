"""Fronteiras temporais, preservação de históricos, reconciliação e falha privada."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import yaml
from src.bronze.expansion import load_temporal_policy, build_temporal_bronze
from src.pipelines.download_home_credit import download_selected
from src.utils.spark import create_spark_session

ROOT = Path(__file__).resolve().parents[1]


class TemporalPolicyTests(unittest.TestCase):
    def test_gaps_overlaps_and_sampling_are_rejected(self):
        policy = yaml.safe_load((ROOT/'configs/temporal_policy_v1.yaml').read_text())
        for change in ('gap','overlap','sampling','window'):
            p = json.loads(json.dumps(policy))
            if change == 'gap': p['windows']['development']['end_exclusive']='2020-05-31'
            if change == 'overlap': p['windows']['development']['end_exclusive']='2020-06-02'
            if change == 'sampling': p['max_cases']=50000
            if change == 'window': p['windows']['public']['start_inclusive']='2020-02-01'
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'policy.yaml';path.write_text(yaml.safe_dump(p))
                with self.subTest(change=change), self.assertRaises(ValueError):load_temporal_policy(path)


class TemporalBronzeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark=create_spark_session(ROOT,app_name='expansion-bronze-tests')

    @classmethod
    def tearDownClass(cls):cls.spark.stop()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.raw=self.root/'data/raw'
        fixtures=self.root/'fixtures';fixtures.mkdir()
        frames={
            'train_base':self.spark.createDataFrame([
                (1,'2019-12-31',0),(2,'2020-01-01',1),(3,'2020-05-31',0),
                (4,'2020-06-01',1),(5,'2020-09-30',0),(6,'2020-10-01',1)],
                'case_id long,date_decision string,target long'),
            'train_history_1':self.spark.createDataFrame([
                (1,0,'2019-01-01',1.0),(2,0,'2018-01-01',None),(2,1,'2021-01-01',2.0),
                (2,1,'2021-01-01',2.0),
                (3,0,'2020-05-31',3.0),(5,0,'2020-09-30',4.0),(6,0,'2020-01-01',5.0)],
                'case_id long,num_group1 long,eventD string,amount double')}
        self.catalog={'dictionary':'feature_definitions.csv','tables':{}}
        payload={}
        for name,frame in frames.items():
            folder=fixtures/name;frame.write.parquet(str(folder))
            # Um shard por arquivo de fixture, preservando nomes de tabela por nível.
            shards=[]
            for i,part in enumerate(sorted(folder.glob('*.parquet'))):
                remote=f'parquet_files/train/{name}_{i}.parquet' if name!='train_base' else 'parquet_files/train/train_base.parquet'
                if name=='train_base':
                    continue
                payload[remote]=part;shards.append({'name':remote,'bytes':part.stat().st_size})
            if name=='train_base':
                single=fixtures/'base_single';frame.coalesce(1).write.parquet(str(single))
                part=next(single.glob('*.parquet'));remote='parquet_files/train/train_base.parquet'
                payload[remote]=part;shards=[{'name':remote,'bytes':part.stat().st_size}]
            self.catalog['tables'][name]=shards
        dictionary=fixtures/'definitions.csv';dictionary.write_text('Variable,Description\namount,fixture\n')
        payload['feature_definitions.csv']=dictionary
        def fetch(remote,stage):
            target=stage/remote;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(payload[remote],target)
        download_selected(self.raw,files=list(payload),fetch=fetch)
        self.policy=load_temporal_policy(ROOT/'configs/temporal_policy_v1.yaml')

    def test_boundaries_history_replay_and_corruption(self):
        manifest,reused=build_temporal_bronze(self.root,self.spark,self.catalog,self.policy)
        self.assertFalse(reused)
        self.assertEqual(manifest['population']['windows'],{'development':2,'evaluation':2,'public':4})
        destination=self.root/'data/bronze/expansion'/manifest['selection_id']
        history=self.spark.read.parquet(str(destination/'tables/train_history_1'))
        self.assertEqual(history.count(),5)
        self.assertEqual(history.filter("eventD < '2020-01-01'").count(),1)
        self.assertEqual(history.filter("eventD > '2020-09-30'").count(),2)
        again,reused=build_temporal_bronze(self.root,self.spark,self.catalog,self.policy)
        self.assertTrue(reused);self.assertEqual(again,manifest)
        part=next((destination/'tables/train_history_1').glob('*.parquet'))
        part.write_bytes(part.read_bytes()+b'corrupt')
        with self.assertRaisesRegex(RuntimeError,'alterada'):
            build_temporal_bronze(self.root,self.spark,self.catalog,self.policy)

    def test_private_failure_never_activates_snapshot_and_retry_succeeds(self):
        with self.assertRaisesRegex(RuntimeError,'injetada'):
            build_temporal_bronze(self.root,self.spark,self.catalog,self.policy,fail_after_table='train_base')
        namespace=self.root/'data/bronze/expansion'
        self.assertEqual([p for p in namespace.iterdir() if p.is_dir() and not p.name.startswith('.')],[])
        failures=list((namespace/'.staging').glob('*/_progress.json'))
        self.assertEqual(json.loads(failures[0].read_text())['status'],'failed')
        manifest,reused=build_temporal_bronze(self.root,self.spark,self.catalog,self.policy)
        self.assertFalse(reused);self.assertEqual(manifest['status'],'passed')
