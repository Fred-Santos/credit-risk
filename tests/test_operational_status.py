from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from src.operation.status import compose, validate_snapshot, observe, load_history, alert_profiles
from src.quality.event_contracts import digest


class OperationalStatusTests(unittest.TestCase):
    def operation(self, status='passed',ident='operation'):
        return {'operation_id':ident,'status':status,'started_at_utc':'2026-11-13T10:00:00Z',
            'options':{'sample':'cohort','mode':'update','batch':'first'},'attempts':[],
            'timing':{'total_seconds':10},'resources':{'peak_process_tree_rss_bytes':100}}

    def snapshot(self):
        identity={'selection_id':'cohort','scope':'operational_analytics_v1'};pub=digest(identity)[:24]
        names=('silver.credit_cases','silver.credit_static','silver.previous_applications','gold.abt','gold.monthly_metrics')
        manifest={'format_version':1,'identity':identity,'publication_id':pub,'status':'passed',
            'tables':{n:{'uri':'s3a://bucket/'+n,'delta_table_id':'table','version':1,'rows':3} for n in names},
            'validations':{'quality':{'status':'passed'}}}
        raw=json.dumps(manifest)
        return {'format_version':1,'pointer':{'publication_id':pub,'manifest_sha256':hashlib.sha256(raw.encode()).hexdigest()},
            'manifest_json':raw,'observed_at_utc':'2026-11-13T10:00:00Z','verification_level':'manifest_and_pointer',
            'availability':'online','is_current_observation':True}

    def policy(self):
        return {'status':'validated','duration_factor':2,'rss_factor':1.5,'profiles':[{'match':self.operation()['options'],
            'duration_warning_seconds':20,'rss_warning_bytes':150}]}

    def test_latest_failure_does_not_hide_approved_publication(self):
        report=compose('cohort',[self.operation('failed','latest'),self.operation()],[],self.snapshot(),self.policy())
        self.assertEqual(report['latest_execution']['status'],'failed')
        self.assertEqual(report['publication']['quality']['status'],'passed')
        self.assertIn('latest_operation_failed',[a['code'] for a in report['alerts']])

    def test_limits_apply_only_to_comparable_success_and_are_not_sla(self):
        op=self.operation();op['timing']['total_seconds']=21;op['resources']['peak_process_tree_rss_bytes']=151
        report=compose('cohort',[op],[],self.snapshot(),self.policy())
        self.assertEqual({a['code'] for a in report['alerts']},{'duration_above_local_baseline','rss_above_local_baseline'})
        op['options']['batch']='another'
        report=compose('cohort',[op],[],self.snapshot(),self.policy())
        self.assertIsNone(report['matched_baseline'])
        self.assertEqual({a['code'] for a in report['alerts']},{'no_comparable_baseline'})

    def test_cached_publication_is_never_current_and_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder);path=repo/'artifacts/f09/status/cohort/last_observed_publication.json'
            path.parent.mkdir(parents=True);path.write_text(json.dumps(self.snapshot()))
            result=observe(repo,'cohort',offline=True)
            self.assertEqual(result['availability'],'cached');self.assertFalse(result['is_current_observation'])
            data=self.snapshot();data['manifest_json']+=' ';path.write_text(json.dumps(data))
            self.assertEqual(observe(repo,'cohort',offline=True)['availability'],'unavailable')

    def test_history_uses_timestamps_not_names_or_mtime_and_flags_invalid_files(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder);path=repo/'artifacts/f09/operations';path.mkdir(parents=True)
            old=self.operation(ident='old');new=self.operation(ident='new');new['started_at_utc']='2026-11-13T11:00:00Z'
            (path/'z.json').write_text(json.dumps(old));(path/'a.json').write_text(json.dumps(new));(path/'broken.json').write_text('{')
            records,errors=load_history(repo,'cohort')
            self.assertEqual([r['operation_id'] for r in records],['new','old']);self.assertEqual(len(errors),1)

    def test_unfinished_report_is_not_a_process_liveness_assertion(self):
        report=compose('cohort',[self.operation('running')],[],{'availability':'unavailable'},self.policy())
        self.assertEqual(len(report['unfinished']),1)
        self.assertIn('unfinished_reports',[a['code'] for a in report['alerts']])
        self.assertIsNone(report['publication'])

    def test_wrong_cohort_or_nonapproved_quality_cannot_be_cached_as_approved(self):
        with self.assertRaises(ValueError):validate_snapshot(self.snapshot(),'other')
        data=self.snapshot();m=json.loads(data['manifest_json']);m['validations']['quality']['status']='failed'
        data['manifest_json']=json.dumps(m);data['pointer']['manifest_sha256']=hashlib.sha256(data['manifest_json'].encode()).hexdigest()
        with self.assertRaises(ValueError):validate_snapshot(data,'cohort')

    def test_policy_is_derived_from_pinned_measurement_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder);(repo/'configs').mkdir();baseline=repo/'baseline.json'
            baseline.write_text(json.dumps(self.operation()))
            config={'version':1,'scope':'local_observational_not_sla','duration_factor':2,'rss_factor':1.5,
                'baselines':[{'report':'baseline.json','sha256':hashlib.sha256(baseline.read_bytes()).hexdigest()}]}
            (repo/'configs/operational_alerts_v1.yaml').write_text(json.dumps(config))
            profile=alert_profiles(repo)['profiles'][0]
            self.assertEqual(profile['duration_warning_seconds'],20);self.assertEqual(profile['rss_warning_bytes'],150)
            baseline.write_text('{}')
            with self.assertRaises(ValueError):alert_profiles(repo)

    def test_invalid_metric_is_reported_instead_of_breaking_status_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder);path=repo/'artifacts/f09/operations';path.mkdir(parents=True)
            record=self.operation();record['timing']['total_seconds']='invalid'
            (path/'bad_metric.json').write_text(json.dumps(record))
            operations,errors=load_history(repo,'cohort')
            self.assertEqual(operations,[]);self.assertEqual(len(errors),1)
            record=self.operation();record['resources']=[]
            (path/'bad_metric.json').write_text(json.dumps(record))
            operations,errors=load_history(repo,'cohort')
            self.assertEqual(operations,[]);self.assertEqual(len(errors),1)
