"""Oráculos pequenos para fidelidade de valores e proveniência."""
import json
from pathlib import Path
import tempfile
import unittest

from src.quality.reconcile_bronze import compare_rows, audit_lineage
from src.utils.run_context import RunContext
from test_bronze_ingestion import publish_fixture

ROOT = Path(__file__).resolve().parents[1]


class ReconciliationSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='reconciliation-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def frame(self, rows):
        return self.spark.createDataFrame(rows, 'case_id long, value double')

    def test_equal_rows_with_nulls_reordering_and_partition_changes(self):
        a = self.frame([(1, None), (2, 1.5)])
        b = self.frame([(2, 1.5), (1, None)]).select('value', 'case_id').repartition(2)
        self.assertTrue(compare_rows(a, b, ['case_id', 'value'])['success'])

    def test_same_count_and_keys_changed_value_detected(self):
        r = compare_rows(self.frame([(1, 100.0)]), self.frame([(1, 101.0)]), ['case_id', 'value'])
        self.assertEqual((r['missing_rows'], r['extra_rows']), (1, 1))

    def test_duplicate_multiplicity_is_preserved(self):
        a = self.frame([(1, 1.0), (1, 1.0), (2, 2.0)])
        b = self.frame([(1, 1.0), (2, 2.0), (2, 2.0)])
        self.assertFalse(compare_rows(a, b, ['case_id', 'value'])['success'])

    def test_incompatible_type_never_cast_silently(self):
        a = self.frame([(1, 1.0)])
        b = self.spark.createDataFrame([(1, '1.0')], 'case_id long, value string')
        with self.assertRaises(ValueError):
            compare_rows(a, b, ['case_id', 'value'])

    def test_wrong_source_path_fails_even_with_equal_business_values(self):
        from pyspark.sql import functions as F
        a = self.frame([(1, 1.0)]).withColumn('_source_file', F.lit('file:///a.parquet'))
        b = self.frame([(1, 1.0)]).withColumn('_source_file', F.lit('file:///b.parquet'))
        self.assertTrue(compare_rows(a, b, ['case_id', 'value'])['success'])
        self.assertFalse(compare_rows(a, b, ['case_id', 'value', '_source_file'])['success'])

    def test_value_change_with_resigned_manifest_blocks_gate_and_reports(self):
        from pyspark.sql import functions as F
        from src.bronze.inputs import bind_sample
        from src.bronze.build_bronze import _output_checksums
        from src.pipelines.run_bronze_mvp import run_bronze
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ctx = RunContext.create(root)
            (root / 'configs').mkdir()
            (root / 'configs/quality_rules_bronze.yaml').write_text((ROOT / 'configs/quality_rules_bronze.yaml').read_text())
            selection = publish_fixture(ctx, 'reconciliation', self.spark)
            bound = bind_sample(ctx, selection)
            first = run_bronze(bound, self.spark)
            self.assertEqual(first['reconciliation']['accepted_rows'], 6)
            batch = next((bound.ctx.bronze_dir / 'train_static_0').glob('ingest_batch=*'))
            stage = root / 'changed'
            # Mantém tipo, chave e metadados: qualidade passa; fidelidade deve falhar.
            self.spark.read.parquet(str(batch)).withColumn('amount', F.lit(999.0)).write.parquet(str(stage))
            for p in batch.glob('*.parquet'):
                p.unlink()
            for p in batch.glob('.*.crc'):
                p.unlink()
            for p in stage.glob('*.parquet'):
                p.replace(batch / p.name)
            manifest_path = batch / '_ingestion.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['output_files'] = _output_checksums(batch)
            manifest_path.write_text(json.dumps(manifest))
            retry = bind_sample(RunContext.create(root), selection)
            with self.assertRaisesRegex(RuntimeError, 'Reconciliação Bronze falhou'):
                run_bronze(retry, self.spark)
            self.assertFalse((retry.ctx.bronze_dir / '_READY.json').exists())
            report = json.loads((retry.ctx.data_quality_dir / 'reconciliation' / f'{retry.ctx.run_id}.json').read_text())
            self.assertEqual(report['accepted_rows'], 0)
            self.assertFalse(report['tables']['train_static_0']['business_values']['success'])


class LineageAuditTests(unittest.TestCase):
    def test_missing_checksum_or_wrong_execution_cannot_pass_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            ctx = RunContext.create(Path(temp))
            event = {'eventType': 'COMPLETE', 'run': {'runId': ctx.run_id},
                     'inputs': [{'namespace': 'file', 'name': 'data/raw/parquet_files/train'}],
                     'outputs': [{'namespace': 'file', 'name': 'data/bronze'}],
                     'artifacts': {'bronzeFiles': {'files': [{'path': 'a', 'sha256': 'hash'}]}}}
            path = Path(temp) / 'lineage.json'
            path.write_text(json.dumps(event))
            self.assertTrue(audit_lineage(ctx, path, {'a': 'hash'})['success'])
            self.assertFalse(audit_lineage(ctx, path, {'a': 'other'})['success'])
            event['run']['runId'] = 'different'
            path.write_text(json.dumps(event))
            self.assertFalse(audit_lineage(ctx, path, {'a': 'hash'})['success'])
