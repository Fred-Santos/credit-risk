"""Invariantes E03–E05 em fixtures sem Home Credit ou credenciais."""
from pathlib import Path
import unittest
from src.expansion.quality import key_audit,compare_keyed
from src.expansion.silver import transform
from src.utils.spark import create_spark_session

ROOT=Path(__file__).resolve().parents[1]


class ExpansionStageSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spark=create_spark_session(ROOT,app_name='expansion-stages-tests')
    @classmethod
    def tearDownClass(cls):cls.spark.stop()

    def test_exact_compare_detects_changed_missing_extra_and_duplicate_keys(self):
        a=self.spark.createDataFrame([(1,1.0),(2,None)],'case_id long,value double')
        b=self.spark.createDataFrame([(1,2.0),(3,None)],'case_id long,value double')
        key_audit(a,['case_id']);key_audit(b,['case_id'])
        r=compare_keyed(a,b,['case_id'])
        self.assertEqual((r['changed_rows'],r['missing_rows'],r['extra_rows']),(1,1,1))
        with self.assertRaises(ValueError):key_audit(a.unionByName(a),['case_id'])

    def test_date_cast_preserves_nulls_and_blocks_invalid_calendar(self):
        rule={'input_schema':{'case_id':'bigint','eventD':'string'},'date_columns':['eventD']}
        a=self.spark.createDataFrame([(1,'2020-05-31'),(2,None)],'case_id long,eventD string')
        b=transform(a,rule)
        self.assertEqual(str(b.orderBy('case_id').first()['eventD']),'2020-05-31')
        self.assertEqual(b.where('eventD IS NULL').count(),1)
        invalid=self.spark.createDataFrame([(1,'2020-02-30')],'case_id long,eventD string')
        with self.assertRaises(ValueError):transform(invalid,rule)

    def test_revisions_handle_resends_stale_events_and_conflicting_payloads(self):
        from src.expansion.revisions import choose_events
        schema='case_id long,num_group1 long,amount double,_source_revision long'
        parent=self.spark.createDataFrame([(1,0,10.0,1)],schema)
        events=self.spark.createDataFrame([(1,0,11.0,2),(1,0,11.0,2),(1,0,10.0,1)],schema)
        chosen=choose_events(events,parent,['case_id','num_group1'])
        self.assertEqual(chosen.count(),1);self.assertEqual(chosen.first()['amount'],11.0)
        self.assertEqual(choose_events(parent,chosen,['case_id','num_group1']).count(),0)
        conflict=self.spark.createDataFrame([(1,0,11.0,2),(1,0,12.0,2)],schema)
        with self.assertRaises(ValueError):choose_events(conflict,parent,['case_id','num_group1'])
        same_rev=self.spark.createDataFrame([(1,0,12.0,1)],schema)
        with self.assertRaises(ValueError):choose_events(same_rev,parent,['case_id','num_group1'])

    def test_hierarchy_weighted_mean_null_and_absent_history(self):
        from src.expansion.features import aggregate_block,sql_oracle,feature_catalog
        from src.expansion.gold import assemble
        from pyspark.sql import functions as F
        frame=self.spark.createDataFrame([(1,0,0,10.0),(1,0,1,20.0),(1,1,0,100.0),(2,0,0,None)],
            'case_id long,num_group1 long,num_group2 long,amount double')
        spec={'key':['case_id','num_group1','num_group2'],'schema':dict(frame.dtypes)}
        rule={'kind':'history','numeric':['amount'],'dates':[],'categories':[]}
        block=aggregate_block(frame,'train_example_2',rule,spec)
        oracle=sql_oracle(self.spark,frame,'train_example_2',rule,spec)
        self.assertTrue(compare_keyed(oracle,block,['case_id'],numeric_tolerance=(1e-8,1e-10))['success'])
        one=block.where('case_id=1').first()
        self.assertAlmostEqual(one['example_2__amount__mean'],130/3)
        self.assertEqual(one['example_2__group_count'],2)
        self.assertIsNone(block.where('case_id=2').first()['example_2__amount__mean'])
        catalog=feature_catalog({'sources':{'train_example_2':rule},'float_comparison':{}},{'tables':{'train_example_2':spec}}, {})
        base=self.spark.createDataFrame([(i,'2020-01-01',202001,1) for i in (1,2,3)],
            'case_id long,date_decision string,MONTH long,WEEK_NUM long').withColumn('date_decision',F.to_date('date_decision'))
        wide=assemble(base,{'source':block},catalog)
        absent=wide.where('case_id=3').first()
        self.assertFalse(absent['example_2__has_source']);self.assertEqual(absent['example_2__observation_count'],0)
        self.assertIsNone(absent['example_2__amount__mean']);self.assertNotIn('target',wide.columns)

    def test_applicant_index_zero_and_deterministic_mode(self):
        from src.expansion.features import aggregate_block,sql_oracle
        f=self.spark.createDataFrame([(1,0,100.0),(1,1,10000.0),(2,1,200.0)],'case_id long,num_group1 long,income double')
        spec={'key':['case_id','num_group1'],'schema':dict(f.dtypes)};rule={'kind':'applicant','columns':['income']}
        result=aggregate_block(f,'train_person_1',rule,spec)
        self.assertEqual(result.where('case_id=1').first()['person_1__income'],100.0)
        self.assertIsNone(result.where('case_id=2').first()['person_1__income'])
        f=self.spark.createDataFrame([(1,0,'b'),(1,1,'a'),(1,2,None)],'case_id long,num_group1 long,status string')
        spec={'key':['case_id','num_group1'],'schema':dict(f.dtypes)};rule={'kind':'history','numeric':[],'dates':[],'categories':['status']}
        block=aggregate_block(f,'train_example_1',rule,spec)
        self.assertEqual(block.first()['example_1__status__mode'],'a')
        self.assertTrue(compare_keyed(sql_oracle(self.spark,f,'train_example_1',rule,spec),block,['case_id'])['success'])


    def test_rejection_diagnostic_preserves_input_and_identifies_key_and_rule(self):
        import tempfile
        from src.expansion.rejections import diagnose
        f=self.spark.createDataFrame([(1,'2020-02-30','raw/a.parquet'),(2,'2020-05-31','raw/a.parquet'),(3,'2020-05-31',None)],
            'case_id long,eventD string,_source_file string')
        spec={'input_schema':dict(f.dtypes),'key':['case_id'],'date_columns':['eventD']}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'diagnostic'
            report=diagnose(f,spec,out,source_manifest_sha256='synthetic')
            self.assertEqual(report['rejected_rows'],2);self.assertEqual(f.count(),3)
            rows={r['case_id']:r['_rejection_reasons'] for r in self.spark.read.parquet(str(out/'records')).collect()}
            self.assertEqual(set(rows),{1,3});self.assertIn('invalid_date:eventD',rows[1])
            self.assertIn('missing_provenance:_source_file',rows[3])



class ExpansionReaderGuardTests(unittest.TestCase):
    def test_holdout_labels_require_opt_in_and_unproven_predictors_block_ml(self):
        from unittest.mock import patch
        from src.expansion.gold import open_abt,open_ml_inputs
        manifest={'ml_ready':False,'eligible_predictors':[]}
        with patch('src.expansion.gold.verify_package',return_value=manifest):
            with self.assertRaises(PermissionError):open_abt(Path('.'),None,Path('.'),'evaluation',include_labels=True)
            with self.assertRaises(ValueError):open_ml_inputs(Path('.'),None,Path('.'),'development')
