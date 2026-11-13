from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import yaml

from src.silver.transforms import (SilverTransformError, load_silver_policy,
    transform_table, transform_snapshot, verify_transformation)

ROOT = Path(__file__).resolve().parents[1]


class SilverPolicyTests(unittest.TestCase):
    def load_changed(self, change):
        policy = yaml.safe_load((ROOT / 'configs/silver_policy_v1.yaml').read_text())
        change(policy)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'policy.yaml'
            path.write_text(yaml.safe_dump(policy))
            return load_silver_policy(path, ROOT / 'configs/contracts/home_credit_v1.yaml',
                                      ROOT / 'notebooks/analise_silver.ipynb')

    def test_unsupported_or_unbound_policy_cannot_enable_destructive_rules(self):
        changes = [lambda p: p['policies'].update(boolean_null_to_false=True),
                   lambda p: p['policies'].update(column_drop='constants'),
                   lambda p: p.update(snapshot_contract_sha256='bad'),
                   lambda p: p.update(notebook_sha256='bad'), lambda p: p.update(version=True)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_changed(change)

    def test_missing_duplicate_or_metadata_date_not_accepted(self):
        changes = [lambda p: p['tables']['train_base'].update(cast_to_date=[]),
                   lambda p: p['tables']['train_base'].update(cast_to_date=['date_decision'] * 2),
                   lambda p: p['tables']['train_base'].update(cast_to_date=['_run_id'])]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_changed(change)


class SilverTransformsSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='silver-transforms-tests')
        cls.spec = {'schema': {'case_id': 'bigint', 'eventD': 'string', 'amount': 'double',
                               'codeM': 'string', 'flag': 'boolean'}, 'key': ['case_id']}

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def frame(self, rows):
        from pyspark.sql import functions as F
        return (self.spark.createDataFrame(rows, 'case_id long, eventD string, amount double, codeM string, flag boolean')
                .withColumn('_run_id', F.lit('original_run'))
                .withColumn('_ingest_date', F.lit('2020-01-01').cast('date'))
                .withColumn('_source_file', F.lit('file:///fixture.parquet'))
                .withColumn('ingest_batch', F.lit('original_batch')))

    def test_valid_leap_date_preserves_numbers_codes_nulls_and_metadata(self):
        frame = self.frame([(1, '2020-02-29', 999.0, 'a55475b1', None),
                            (2, '2019-01-01', -1.5, 'Q3_9_meet', False),
                            (3, None, 3e10, 'P1_2_3', True)])
        after, report = transform_table('example', frame, self.spec, ['eventD'])
        self.assertEqual(dict(after.dtypes)['eventD'], 'date')
        self.assertEqual(report['dates']['eventD']['converted_non_nulls'], 2)
        self.assertEqual(report['dates']['eventD']['input_nulls'], 1)
        self.assertEqual(report['dates']['eventD']['new_nulls'], 0)
        self.assertTrue(verify_transformation(frame, after, self.spec, ['eventD'])['success'])
        rows = after.orderBy('case_id').collect()
        self.assertEqual(str(rows[0].eventD), '2020-02-29')
        self.assertEqual([(r.amount, r.codeM, r.flag, r._run_id) for r in rows],
                         [(999.0, 'a55475b1', None, 'original_run'),
                          (-1.5, 'Q3_9_meet', False, 'original_run'), (3e10, 'P1_2_3', True, 'original_run')])

    def test_invalid_dates_block_under_ansi_and_legacy_settings(self):
        bad = ['2019-02-29', '2020-02-30', '', '2020-1-01', ' 2020-01-01', '2020-01-01T00:00:00', '9999-99-99']
        frame = self.frame([(i, date, None, None, None) for i, date in enumerate(bad)])
        prior = {k: self.spark.conf.get(k) for k in ['spark.sql.ansi.enabled', 'spark.sql.legacy.timeParserPolicy']}
        try:
            for ansi, parser in [('true', 'CORRECTED'), ('false', 'LEGACY'), ('false', 'EXCEPTION')]:
                self.spark.conf.set('spark.sql.ansi.enabled', ansi)
                self.spark.conf.set('spark.sql.legacy.timeParserPolicy', parser)
                with self.subTest(ansi=ansi, parser=parser), self.assertRaises(SilverTransformError) as caught:
                    transform_table('example', frame, self.spec, ['eventD'])
                self.assertEqual(caught.exception.report['invalid_rows'], len(bad))
                self.assertEqual(caught.exception.report['invalid_date_cells'], len(bad))
        finally:
            for key, value in prior.items():
                self.spark.conf.set(key, value)

    def test_empty_and_all_null_optional_dates_do_not_create_fake_losses(self):
        for rows in [[], [(1, None, None, None, None)]]:
            before = self.frame(rows)
            after, metrics = transform_table('example', before, self.spec, ['eventD'])
            self.assertEqual(metrics['invalid_rows'], 0)
            self.assertEqual(metrics['dates']['eventD']['converted_non_nulls'], 0)
            self.assertEqual(after.count(), len(rows))
            self.assertTrue(verify_transformation(before, after, self.spec, ['eventD'])['success'])

    def test_one_invalid_table_blocks_entire_snapshot_with_counts(self):
        frames = {'good': self.frame([(1, '2020-01-01', None, None, None)]),
                  'bad': self.frame([(2, 'invalid', None, None, None)])}
        contract = {'tables': {name: self.spec for name in frames}}
        policy = {'tables': {name: {'cast_to_date': ['eventD']} for name in frames}}
        with self.assertRaises(SilverTransformError) as caught:
            transform_snapshot(frames, contract, policy)
        report = caught.exception.report
        self.assertEqual(report['accepted_rows'], 0)
        self.assertEqual(report['discarded_rows'], 0)
        self.assertEqual(report['tables']['bad']['invalid_rows'], 1)
        self.assertTrue(report['tables']['good']['preservation']['success'])

    def test_preservation_proof_detects_payload_change_or_removed_row(self):
        from pyspark.sql import functions as F
        before = self.frame([(1, '2020-01-01', 999.0, 'a55475b1', None)])
        after, _ = transform_table('example', before, self.spec, ['eventD'])
        for bad in [after.withColumn('amount', F.lit(0.0)), after.limit(0),
                    after.withColumn('flag', F.lit(False))]:
            self.assertFalse(verify_transformation(before, bad, self.spec, ['eventD'])['success'])

    def test_wrong_schema_and_timezone_require_explicit_resolution(self):
        frame = self.frame([(1, '2020-01-01', None, None, None)])
        with self.assertRaises(ValueError):
            transform_table('example', frame.drop('amount'), self.spec, ['eventD'])
        previous = self.spark.conf.get('spark.sql.session.timeZone')
        try:
            self.spark.conf.set('spark.sql.session.timeZone', 'America/Sao_Paulo')
            with self.assertRaisesRegex(ValueError, 'UTC'):
                transform_table('example', frame, self.spec, ['eventD'])
        finally:
            self.spark.conf.set('spark.sql.session.timeZone', previous)
