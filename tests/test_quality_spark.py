"""Integração opcional: requer pyspark e Java configurados."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from src.quality.engine import evaluate, run_checks
from src.utils.run_context import RunContext


@unittest.skipUnless(importlib.util.find_spec('pyspark'), 'PySpark não instalado')
class SparkQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession
        cls.spark = (SparkSession.builder.master('local[1]').appName('quality-tests')
                     .config('spark.sql.shuffle.partitions', '1').getOrCreate())

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_duplicate_key_across_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'dataset'
            for batch in ['a', 'b']:
                self.spark.createDataFrame([(1,)], ['case_id']).write.parquet(str(path / f'ingest_batch={batch}'))
            df = self.spark.read.parquet(str(path))
            self.assertFalse(evaluate(df, {'type': 'unique', 'columns': ['case_id']}, self.spark, Path(temp))['success'])

    def test_nulls_and_target_domain(self):
        df = self.spark.createDataFrame([(1, 0), (None, 2)], 'case_id long, target long')
        self.assertFalse(evaluate(df, {'type': 'not_null', 'columns': ['case_id']}, self.spark, Path('.'))['success'])
        self.assertFalse(evaluate(df, {'type': 'allowed_values', 'column': 'target', 'values': [0, 1]}, self.spark, Path('.'))['success'])
        valid = self.spark.createDataFrame([(1, 1)], 'case_id long, target long')
        self.assertTrue(evaluate(valid, {'type': 'allowed_values', 'column': 'target', 'values': [0, 1]}, self.spark, Path('.'))['success'])

    def test_orphan_case_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.spark.createDataFrame([(1,)], ['case_id']).write.parquet(str(root / 'train_base'))
            check = {'type': 'foreign_key', 'columns': ['case_id'], 'reference': 'train_base'}
            valid = self.spark.createDataFrame([(1,)], ['case_id'])
            orphan = self.spark.createDataFrame([(2,)], ['case_id'])
            self.assertTrue(evaluate(valid, check, self.spark, root)['success'])
            self.assertFalse(evaluate(orphan, check, self.spark, root)['success'])

    def test_real_bronze_after_unit_doubles(self):
        # O import deve usar funções PySpark reais, mesmo após a suíte unitária.
        from src.bronze.build_bronze import build_bronze_from_raw
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'configs').mkdir()
            (root / 'configs/paths.yaml').write_text(
                'data: {raw: inputs, bronze: outputs/bronze}\ndocs: {root: reports}\n')
            (root / 'configs/quality_rules_bronze.yaml').write_text(
                'tables:\n  - pattern: "*"\n    checks:\n      - type: non_empty\n')
            ctx = RunContext.create(root)
            source = ctx.raw_dir / 'parquet_files/train/train_base'
            self.spark.createDataFrame([(101,), (102,)], ['case_id']).write.parquet(str(source))
            self.assertEqual(build_bronze_from_raw(ctx, self.spark), ['outputs/bronze/train_base'])
            output = self.spark.read.parquet(str(ctx.bronze_dir / 'train_base'))
            self.assertEqual(sorted(row.case_id for row in output.collect()), [101, 102])
            self.assertEqual(output.select('_run_id').distinct().first()[0], ctx.run_id)
            self.assertEqual(build_bronze_from_raw(ctx, self.spark), [])
            report = run_checks(ctx, self.spark, layer='bronze')
            self.assertTrue(Path(report['json']).is_relative_to(root / 'reports/data_quality'))
