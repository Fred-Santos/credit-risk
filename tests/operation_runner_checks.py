import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from unittest.mock import Mock
from botocore.exceptions import EndpointConnectionError, ClientError
from src.operation.runner import supervise, classify


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name);(self.repo/'configs').mkdir()
        (self.repo/'configs/paths.yaml').write_bytes(Path('configs/paths.yaml').read_bytes())
        self.options=dict(sample='cohort',source_report='source.json',mode='rebuild',batch=None)
        self.service=Mock();self.service.status.return_value={'status':'stopped'}
        self.spark=Mock();self.executor=Mock(return_value={'status':'passed'})

    def run_case(self, **kwargs):
        result=supervise(self.repo,self.options,service_factory=lambda _:self.service,
            spark_factory=lambda *a,**k:self.spark,executor=self.executor,sleep=lambda _:None,**kwargs)
        report=json.loads(Path(result['report']).read_text())
        self.assertAlmostEqual(sum(report['timing']['stage_seconds'].values()),report['timing']['total_seconds'],places=6)
        for attempt in report['attempts']:
            self.assertAlmostEqual(sum(attempt['timing']['stage_seconds'].values()),attempt['timing']['total_seconds'],places=6)
        self.assertIn('peak_process_tree_rss_bytes',report['resources'])
        return result,report

    def test_transient_resumes_with_same_logical_identity_and_new_attempt_ids(self):
        self.executor.side_effect=[EndpointConnectionError(endpoint_url='http://127.0.0.1'),{'status':'passed'}]
        result,report=self.run_case()
        self.assertEqual(result['exit_code'],0);self.assertEqual(len(report['attempts']),2)
        calls=self.executor.call_args_list
        self.assertEqual(calls[0].kwargs['operation_id'],calls[1].kwargs['operation_id'])
        self.assertNotEqual(calls[0].args[0].run_id,calls[1].args[0].run_id)
        self.assertEqual(self.spark.stop.call_count,2);self.assertEqual(self.service.stop.call_count,2)

    def test_contract_error_is_not_retried(self):
        self.executor.side_effect=ValueError('schema inválido')
        result,report=self.run_case();self.assertEqual(result['exit_code'],3)
        self.assertEqual(len(report['attempts']),1)
        from src.quality.silver_contracts import SilverContractError
        from src.gold.quality import GoldQualityError
        for error in (SilverContractError({'status':'failed'}),GoldQualityError({'status':'failed'})):
            self.executor.side_effect=error
            result,report=self.run_case()
            self.assertEqual(result['exit_code'],3)
            self.assertEqual(report['attempts'][0]['category'],'quality_rejected')
            self.assertEqual(len(report['attempts']),1)

    def test_recoverable_exhaustion_is_bounded(self):
        self.executor.side_effect=EndpointConnectionError(endpoint_url='http://127.0.0.1')
        result,report=self.run_case(max_attempts=3)
        self.assertEqual(result['exit_code'],5);self.assertEqual(len(report['attempts']),3)

    def test_initialization_failure_gets_report(self):
        self.service.start.side_effect=FileNotFoundError('binário ausente')
        result,report=self.run_case()
        self.assertEqual(result['exit_code'],3);self.assertEqual(report['stage'],'service_start')
        self.executor.assert_not_called();self.service.stop.assert_called_once()
        result=supervise(self.repo,self.options,service_factory=Mock(side_effect=ValueError('configuração')))
        self.assertEqual(result['exit_code'],3)
        self.assertEqual(json.loads(Path(result['report']).read_text())['stage'],'service_configuration')
        self.service.start.side_effect=None
        result=supervise(self.repo,self.options,service_factory=lambda _:self.service,
            spark_factory=Mock(side_effect=RuntimeError('JVM ausente')))
        self.assertEqual(result['exit_code'],1)
        self.assertEqual(json.loads(Path(result['report']).read_text())['stage'],'spark_start')
        (self.repo/'configs/paths.yaml').write_text('[]')
        result,report=self.run_case()
        self.assertEqual(result['exit_code'],3)
        self.assertEqual(report['stage'],'context_configuration')
        self.assertIn('finished_at_utc',report)


    def test_cleanup_never_hides_primary_or_starts_another_writer(self):
        self.executor.side_effect=EndpointConnectionError(endpoint_url='http://127.0.0.1')
        self.spark.stop.side_effect=RuntimeError('JVM não encerrou')
        result,report=self.run_case()
        self.assertEqual(result['exit_code'],5);self.assertEqual(len(report['attempts']),1)
        self.assertEqual(report['attempts'][0]['category'],'temporary_access')
        self.assertEqual(len(report['attempts'][0]['cleanup_errors']),1)

    def test_existing_service_is_preserved_and_stages_recorded(self):
        self.service.status.return_value={'status':'running'}
        def execute(*args,**kwargs):kwargs['on_stage']('publication');return {'status':'passed'}
        self.executor.side_effect=execute
        result,report=self.run_case();self.service.stop.assert_not_called()
        self.assertEqual(result['status'],'passed')
        self.assertEqual(report['attempts'][0]['stages'][-1]['stage'],'publication')
        self.assertIn('finished_at_utc',report)

    def test_cancellation_and_cleanup_failure_have_nonzero_exit(self):
        self.executor.side_effect=KeyboardInterrupt()
        result,report=self.run_case();self.assertEqual(result['exit_code'],130)
        self.executor.side_effect=None;self.spark.stop.side_effect=RuntimeError('stop')
        result,report=self.run_case();self.assertEqual(result['exit_code'],1)
        self.assertEqual(report['attempts'][0]['category'],'cleanup_failed')

    def test_status_codes_and_policy_validation(self):
        for status,retry in [(403,False),(412,False),(429,True),(503,True)]:
            error=ClientError({'ResponseMetadata':{'HTTPStatusCode':status},'Error':{'Code':str(status)}},'PutObject')
            self.assertEqual(classify(error,'publication')[1],retry)
        self.assertFalse(classify(RuntimeError('SocketTimeoutException in text'),'publication')[1])
        for count in (0,4):
            with self.assertRaises(ValueError):self.run_case(max_attempts=count)
        with self.assertRaises(ValueError):
            self.run_case(reports_directory=self.repo.parent)


if __name__=='__main__':unittest.main(verbosity=2)
