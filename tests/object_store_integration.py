"""F08 real: SeaweedFS + S3A + Delta, dados sintéticos e namespaces descartáveis."""
from functools import reduce
import json
from pathlib import Path
import sys
import unittest
import uuid

import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from publication_fixture import fixture_frames
from src.bronze.build_bronze import _ingestion_lock
from src.bronze.event_parquet import encode_events,revision_index
from src.gold.model import load_gold_contract
from src.gold.publish import prepare_gold
from src.object_store.client import ObjectClient
from src.object_store.fixtures import capability_probe,lifecycle_fixture,temporary_objects
from src.object_store.incremental import ObjectIncremental
from src.object_store.publication import (publish_object_snapshot,verify_publication,registry_key,current,
    activate_object_publication,open_object_publication)
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.pipelines.download_home_credit import sha256
from src.pipelines.run_incremental_demo import with_ordinals
from src.publication.evolution import prepare_silver
from src.publication.protocol import InjectedFailure,NoPublicationError,fail_at
from src.quality.bronze_contract import METADATA
from src.quality.reconcile_bronze import compare_rows
from src.quality.silver_contracts import SilverContractError
from src.silver.incremental import reconstruct
from src.silver.initial_delta import TABLES
from src.utils.run_context import RunContext


class ObjectStorageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service=ObjectService(ROOT)
        cls.preexisting=cls.service.status()['status']=='running'
        cls.service.start()
        cls.fixture=temporary_objects(ROOT);cls.client=cls.fixture.__enter__()
        cls.registry=registry_key(cls.client,'a'*24)
        cls.spark=create_object_spark(ROOT,app_name='f08-object-integration')
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions','2')
        cls.data={}
        for label,kwargs in [('baseline',{}),('corrected',{'corrected':True}),('late',{'corrected':True,'late':True})]:
            cls.data[label],cls.plan=fixture_frames(cls.spark,**kwargs)
        cls.spec=load_gold_contract(ROOT/'configs/contracts/gold_v1.yaml',ROOT/'configs/contracts/silver_managed_v2.yaml')
        cls.local_fixture=ROOT/'artifacts/f08/testing'/uuid.uuid4().hex/'fixture.json'
        cls.local_fixture.parent.mkdir(parents=True);cls.local_fixture.write_text('{"synthetic_fixture":true}\n')
        cls.fingerprints={cls.local_fixture.relative_to(ROOT).as_posix():sha256(cls.local_fixture)}
        cls.baseline,cls.base_frames=cls.publish_class('baseline',parent=None)

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop();cls.fixture.__exit__(None,None,None)
        cls.local_fixture.unlink();cls.local_fixture.parent.rmdir()
        if not cls.preexisting:cls.service.stop()

    @classmethod
    def publish_class(cls,label,*,data_label='baseline',parent='baseline',hook=None,frames=None):
        data=cls.data[data_label] if frames is None else frames
        counts={n:f.count() for n,f in data.items()}
        previous=None
        if parent is not None:
            manifest,loaded=verify_publication(cls.client,cls.registry,cls.baseline['publication_id'],cls.spark)
            previous={'manifest':manifest,'frames':loaded,'silver':{n:loaded['silver.'+n] for n in cls.plan['tables']}}
        identity={'scope':'object_analytics_v1','selection_id':'a'*24,'snapshot':label,'fixture':cls.client.config['prefix']}
        def builder(tx):
            silver=prepare_silver(tx,data,cls.plan,counts)
            tx.hook('between_silver_and_gold')
            prepare_gold(tx,silver,cls.spec,parent=previous)
        manifest,_=publish_object_snapshot(RunContext.create(ROOT),cls.client,cls.registry,cls.spark,identity,
            cls.fingerprints,builder,hook=hook)
        return manifest,verify_publication(cls.client,cls.registry,manifest['publication_id'],cls.spark)[1]

    def setUp(self):
        activate_object_publication(RunContext.create(ROOT),self.client,self.registry,self.spark,self.baseline['publication_id'])

    def test_01_conformance_authentication_list_and_conditional_put(self):
        self.assertEqual(capability_probe(ROOT)['status'],'passed')
        self.assertTrue(all(r['host']=='127.0.0.1' for r in self.service.listeners()))
        with self.assertRaises(NoPublicationError):current(self.client,self.registry+'/empty')
        with open_object_publication(self.client,self.registry,self.spark) as (_,frames):
            self.assertEqual(frames['gold.abt'].count(),3)
            self.assertEqual(frames['gold.abt'].filter('case_id=1').first().previous_application_count,2)
            self.assertEqual({r._silver_contract_version for r in frames['silver.credit_cases'].collect()},{2})

    def test_02_silver_post_commit_failure_preserves_current_and_resumes(self):
        previous=current(self.client,self.registry)[0]
        with self.assertRaises(InjectedFailure):
            self.publish_class('silver_failure',data_label='corrected',hook=fail_at('after_commit:silver.credit_static:create'))
        self.assertEqual(current(self.client,self.registry)[0],previous)
        manifest,frames=self.publish_class('silver_failure',data_label='corrected')
        self.assertEqual({t['version'] for n,t in manifest['tables'].items() if n.startswith('silver.')},{2})
        self.assertEqual(frames['gold.abt'].filter('case_id=1').first().static_annuity,11)

    def test_03_gold_post_merge_failure_resumes_without_second_commit(self):
        previous=current(self.client,self.registry)[0]
        with self.assertRaises(InjectedFailure):
            self.publish_class('gold_failure',data_label='corrected',hook=fail_at('after_commit:gold.abt:merge'))
        self.assertEqual(current(self.client,self.registry)[0],previous)
        manifest,_=self.publish_class('gold_failure',data_label='corrected')
        self.assertEqual(manifest['tables']['gold.abt']['version'],1)
        self.assertEqual(manifest['details']['gold_update']['commits_this_attempt'],{'inserts':0,'updates':0})
        repeated,_=self.publish_class('gold_failure',data_label='corrected')
        self.assertEqual(repeated,manifest)

    def test_04_manifest_pointer_windows_and_history(self):
        for i,point in enumerate(('before_manifest','before_pointer','after_pointer')):
            previous=current(self.client,self.registry)[0]
            with self.assertRaises(InjectedFailure):self.publish_class('pointer_'+str(i),data_label='corrected',hook=fail_at(point))
            if point!='after_pointer':self.assertEqual(current(self.client,self.registry)[0],previous)
            manifest,_=self.publish_class('pointer_'+str(i),data_label='corrected')
            self.assertEqual(current(self.client,self.registry)[0]['publication_id'],manifest['publication_id'])
        activate_object_publication(RunContext.create(ROOT),self.client,self.registry,self.spark,self.baseline['publication_id'])
        with open_object_publication(self.client,self.registry,self.spark) as (_,frames):
            self.assertEqual(frames['gold.abt'].filter('case_id=1').first().static_annuity,10)

    def test_05_quality_and_schema_block_publication(self):
        from pyspark.sql import functions as F
        previous=current(self.client,self.registry)[0]
        bad={**self.data['baseline'],'credit_cases':self.data['baseline']['credit_cases'].withColumn('target',F.lit(7).cast('long'))}
        with self.assertRaises(SilverContractError):self.publish_class('quality_failure',frames=bad)
        drift={**self.data['baseline'],'credit_cases':self.data['baseline']['credit_cases'].withColumn('extra',F.lit(1))}
        with self.assertRaises(ValueError):self.publish_class('schema_failure',frames=drift)
        self.assertEqual(current(self.client,self.registry)[0],previous)
        with self.assertRaises(InjectedFailure):
            self.publish_class('between_tables',data_label='corrected',hook=fail_at('between_silver_and_gold'))
        self.assertEqual(current(self.client,self.registry)[0],previous)

    def test_06_service_outage_after_private_commit_and_restart(self):
        previous=current(self.client,self.registry)[0]
        def stop_after_commit(stage):
            if stage=='after_commit:gold.abt:merge':
                self.service.stop();raise InjectedFailure('Serviço parado após commit privado')
        try:
            with self.assertRaises(InjectedFailure):self.publish_class('outage',data_label='corrected',hook=stop_after_commit)
            with self.assertRaises(Exception):self.client.get(self.registry+'/_CURRENT.json')
            with self.assertRaises(Exception):self.publish_class('outage_attempt',parent=None)
        finally:self.service.start()
        self.assertEqual(current(self.client,self.registry)[0],previous)
        manifest,frames=self.publish_class('outage',data_label='corrected')
        self.assertEqual(manifest['tables']['gold.abt']['version'],1)
        self.assertEqual(frames['gold.abt'].filter('case_id=1').first().previous_amount_sum,6)

    def test_07_single_host_writer_exclusion(self):
        with _ingestion_lock(self.service.control,'.writer.lock'):
            with self.assertRaises(OSError):self.publish_class('concurrent',parent=None)

    def test_08_published_file_corruption_is_rejected(self):
        manifest,_=self.publish_class('corrupt_fixture',data_label='corrected')
        table=manifest['tables']['gold.abt']
        file=next(name for name in table['files'] if name.endswith('.parquet'))
        self.client.s3.put_object(Bucket=self.client.bucket,Key=table['key']+'/'+file,Body=b'corrupt synthetic fixture')
        with self.assertRaises(ValueError):verify_publication(self.client,self.registry,manifest['publication_id'],self.spark)

    def test_09_native_incremental_merge_retry_and_frozen_reconstruction(self):
        from pyspark.sql import functions as F
        snapshot={'tables':{}};policy={'tables':{}};bronze={}
        reverse={target:source for source,target in TABLES.items()}
        for name,frame in self.data['baseline'].items():
            source=reverse[name];business=[c for c in self.plan['tables'][name]['schema'] if c not in METADATA]
            dates=[c for c,t in frame.dtypes if t=='date' and c in business]
            candidate=frame.select(*business,*METADATA)
            for column in dates:candidate=candidate.withColumn(column,F.col(column).cast('string'))
            bronze[source]=candidate
            snapshot['tables'][source]={'schema':dict(candidate.select(*business).dtypes),
                'key':self.plan['tables'][name]['key'],'required_non_null':self.plan['tables'][name]['required_non_null'][:len(business)]}
            policy['tables'][source]={'cast_to_date':dates,'key':self.plan['tables'][name]['key']}
        contract=yaml.safe_load((ROOT/'configs/contracts/home_credit_events_v1.yaml').read_text())
        binding={'selection_id':'a'*24,'fixture':True};stream='s3_fixture'
        def packet(label,sources,revision):
            frames={name:encode_events(with_ordinals(frame,snapshot['tables'][name]['key']),contract,snapshot,
                selection_id='a'*24,stream_id=stream,batch_id=label,table=name,revision=revision,
                scenario='late_arrival',origin='synthetic_fixture') for name,frame in sources.items()}
            return {'binding':binding,'stream_id':stream,'batch_id':label,'packet_sha256':label},frames
        initial=packet('initial',bronze,1)
        corrected={name:frame.limit(0) for name,frame in bronze.items()}
        corrected['train_static_0']=bronze['train_static_0'].filter('case_id=1').withColumn('annuity_780A',F.lit(11.0))
        corrected['train_applprev_1']=bronze['train_applprev_1'].filter('case_id=1 AND num_group1=0').withColumn('credamount_590A',F.lit(6.0))
        update=packet('corrected',corrected,2)
        history={name:initial[1][name].unionByName(update[1][name]) for name in TABLES}
        indices=[revision_index(f) for f in history.values()]
        identity={'source_binding':binding,'source_stream_id':stream,'fixture':True}
        engine=ObjectIncremental(self.client,self.spark,self.client.config['prefix']+'/working/native',identity,self.plan)
        with self.assertRaises(InjectedFailure):
            engine.apply(initial[0],initial[1],indices,snapshot,policy,'fixture',hook=fail_at('after_incremental_commit:credit_cases'))
        engine.apply(initial[0],initial[1],indices,snapshot,policy,'fixture')
        engine.apply(update[0],update[1],indices,snapshot,policy,'fixture')
        versions=engine.verify();retry=engine.apply(initial[0],initial[1],indices,snapshot,policy,'fixture')
        self.assertEqual(versions,retry['versions_after'])
        expected=reconstruct(history,snapshot,policy)
        proofs={n:compare_rows(expected[n],engine.read()[n],expected[n].columns) for n in expected}
        self.assertTrue(all(p['success'] for p in proofs.values()))
        engine.freeze({'final':versions},{'status':'passed','tables':proofs})
        self.assertEqual(engine.verify_frozen()['versions'],versions)
        with self.assertRaises(ValueError):engine.apply(update[0],update[1],indices,snapshot,policy,'fixture')

    def test_10_temporary_lab_restart_and_removal(self):
        result=lifecycle_fixture(ROOT)
        self.assertTrue(result['internally_created_lab_removed'])
        self.assertFalse(result['real_data_removed'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ObjectStorageIntegrationTests))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
