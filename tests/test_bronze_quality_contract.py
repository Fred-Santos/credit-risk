"""Qualidade de snapshot: schemas mínimos sintéticos, Spark e filesystem reais."""
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from src.quality.engine import load_rules, run_checks
from src.utils.run_context import RunContext
from test_bronze_ingestion import publish_fixture

ROOT = Path(__file__).resolve().parents[1]


class QualityConfigurationTests(unittest.TestCase):
    def test_invalid_configuration_never_becomes_warning(self):
        cases = [
            {'defaults': []}, {'tables': [{'pattern': '*', 'checks': []}]},
            {'required_datasets': 'train_base'}, {'snapshot_contract': []},
            {'tables': [{'pattern': '*', 'checks': [{'type': 'unique', 'columns': []}]}]},
            {'tables': [{'pattern': '*', 'checks': [{'type': 'not_null', 'columns': 'case_id'}]}]},
            {'tables': [{'pattern': '*', 'checks': [{'type': 'foreign_key', 'columns': ['x'], 'reference': '../x'}]}]},
            {'tables': [{'pattern': '*', 'checks': [{'type': 'allowed_values', 'column': 'x', 'values': []}]}]},
            {'tables': [{'pattern': '*', 'checks': [{'type': 'non_empty', 'typo': True}]}]},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'rules.yaml'
            for config in cases:
                config = {'defaults': {'action_on_fail': 'warn'}, 'tables': [], **config}
                path.write_text(yaml.safe_dump(config))
                with self.subTest(config=config), self.assertRaises(ValueError):
                    load_rules(path)


class BronzeContractSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='bronze-contract-quality-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = RunContext.create(Path(self.temp.name))
        (self.ctx.repo_root / 'configs').mkdir()
        (self.ctx.repo_root / 'configs/quality_rules_bronze.yaml').write_text(
            (ROOT / 'configs/quality_rules_bronze.yaml').read_text())
        selection = publish_fixture(self.ctx, 'quality')
        self.sample = self.ctx.sample_dir / selection
        self.frames = {
            'train_base': self.spark.createDataFrame([(1, '2020-01-01', 202001, 0, 0)],
                'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long'),
            'train_static_0': self.spark.createDataFrame([(1, None)], 'case_id long, amount double'),
            'train_applprev_1': self.spark.createDataFrame([], 'case_id long, num_group1 long, amount double'),
        }

    def write(self):
        from pyspark.sql import functions as F
        for name, df in self.frames.items():
            df = (df.withColumn('_run_id', F.lit('fixture'))
                  .withColumn('_source_file', F.lit('fixture.parquet'))
                  .withColumn('_ingest_date', F.lit('2020-01-01').cast('date')))
            df.coalesce(1).write.parquet(str(self.ctx.bronze_dir / name / 'ingest_batch=fixture'))

    def check(self):
        try:
            run_checks(self.ctx, self.spark, layer='bronze')
        except RuntimeError:
            pass
        path = self.ctx.data_quality_dir / 'bronze_results' / f'{self.ctx.run_id}_bronze_checks.json'
        return json.loads(path.read_text())

    def test_empty_optional_history_and_optional_null_pass(self):
        self.write()
        self.assertEqual(self.check()['failed_checks'], 0)

    def test_missing_auxiliary_and_unexpected_dataset_block(self):
        self.frames['unexpected'] = self.frames.pop('train_static_0')
        self.write()
        failed = {r['check'] for r in self.check()['results'] if not r['success']}
        self.assertTrue({'dataset_present', 'dataset_in_contract'} <= failed)

    def test_schema_drift_and_incompatible_type_block(self):
        from pyspark.sql import functions as F
        self.frames['train_static_0'] = self.frames['train_static_0'].withColumn('amount', F.lit('wrong')).withColumn('extra', F.lit(0))
        self.write()
        failed = [r for r in self.check()['results'] if r['check'] == 'exact_schema' and not r['success']]
        self.assertEqual(failed[0]['extra_columns'], ['extra'])
        self.assertIn('amount', failed[0]['type_mismatches'])

    def test_calendar_target_and_missing_static_coverage_block(self):
        self.frames['train_base'] = self.spark.createDataFrame(
            [(1, '2020-02-30', 202001, -1, 2), (2, '2020-01-01', 202001, 0, 0)],
            self.frames['train_base'].schema)
        self.write()
        failed = {r['check'] for r in self.check()['results'] if not r['success']}
        self.assertTrue({'base_calendar', 'allowed_values', 'parent_coverage'} <= failed)

    def test_global_duplicates_and_orphans_block(self):
        self.frames['train_applprev_1'] = self.spark.createDataFrame(
            [(9, 0, None), (9, 0, None)], self.frames['train_applprev_1'].schema)
        self.write()
        failed = {r['check'] for r in self.check()['results'] if not r['success']}
        self.assertTrue({'unique', 'foreign_key'} <= failed)

    def test_unreadable_dataset_blocks_with_report(self):
        self.write()
        path = self.ctx.bronze_dir / 'train_applprev_1'
        for file in path.rglob('*.parquet'):
            file.write_bytes(b'not parquet')
        failed = {r['check'] for r in self.check()['results'] if not r['success']}
        self.assertIn('readable', failed)
