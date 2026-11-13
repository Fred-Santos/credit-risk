from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest

import yaml

from src.quality.silver_contracts import (DOMAINS, RELATIONSHIPS, SilverContractError,
    load_silver_contract, validate_silver_frames)
from src.quality.bronze_contract import METADATA

ROOT = Path(__file__).resolve().parents[1]


class SilverContractConfigurationTests(unittest.TestCase):
    def load_changed(self, change):
        config = yaml.safe_load((ROOT / 'configs/contracts/silver_initial_v1.yaml').read_text())
        change(config)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'silver.yaml'
            path.write_text(yaml.safe_dump(config))
            return load_silver_contract(path, ROOT / 'configs/contracts/home_credit_v1.yaml',
                ROOT / 'configs/silver_policy_v1.yaml', ROOT / 'notebooks/analise_silver.ipynb')

    def test_hashes_and_unsupported_rules_cannot_be_bypassed(self):
        for change in [lambda c: c.update(snapshot_contract_sha256='bad'),
                       lambda c: c.update(silver_policy_sha256='bad'),
                       lambda c: c['policies'].update(required_nulls='warn'),
                       lambda c: c.update(version=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_changed(change)

    def test_schema_derived_from_fixed_inputs_not_writer_manifest(self):
        plan = self.load_changed(lambda c: None)
        self.assertEqual(sum(len(t['schema']) for t in plan['tables'].values()), 226)
        self.assertEqual(sum(t == 'date' for s in plan['tables'].values() for t in s['schema'].values()), 26)
        for change in [lambda c: c['table_bindings'].update(credit_static='train_base'),
                       lambda c: c['relationships']['previous_applications'].update(full_parent_coverage=True),
                       lambda c: c.update(unknown='ignored')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_changed(change)


class SilverContractSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='silver-contract-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        from pyspark.sql import functions as F
        self.frames = {
            'credit_cases': self.spark.createDataFrame([
                (1, date(2020, 1, 1), 202001, 0, 0), (2, date(2020, 1, 2), 202001, 1, 1),
                (3, date(2020, 1, 3), 202001, 2, 0)],
                'case_id long, date_decision date, MONTH long, WEEK_NUM long, target long'),
            'credit_static': self.spark.createDataFrame([
                (1, 999.0, 'a55475b1', date(2019, 12, 1)), (2, None, None, date(2021, 1, 1)),
                (3, -1.0, 'Q3_9_meet', None)], 'case_id long, amount double, codeM string, offerD date'),
            'previous_applications': self.spark.createDataFrame([
                (1, 0, date(2019, 12, 1), 10.5), (1, 1, date(2020, 1, 2), 99.0),
                (2, 0, None, None)], 'case_id long, num_group1 long, observedD date, amount double')}
        self.plan = {'tables': {}, 'domains': DOMAINS}
        for name, frame in self.frames.items():
            fields = dict(frame.dtypes)
            dates = [c for c, dtype in fields.items() if dtype == 'date']
            required = list(fields) if name == 'credit_cases' else ['case_id']
            if name == 'previous_applications':
                required.append('num_group1')
            spec = {'schema': {**fields, **METADATA}, 'grain': 'synthetic_fixture',
                    'key': ['case_id', 'num_group1'] if name == 'previous_applications' else ['case_id'],
                    'required_non_null': required + list(METADATA), 'minimum_rows': 0 if name == 'previous_applications' else 1,
                    'dates': dates, 'relationship': RELATIONSHIPS.get(name)}
            self.plan['tables'][name] = spec
            self.frames[name] = (frame.withColumn('_run_id', F.lit('original_run'))
                .withColumn('_source_file', F.lit('file:///fixture.parquet'))
                .withColumn('_ingest_date', F.lit('2020-01-01').cast('date'))
                .withColumn('ingest_batch', F.lit('original_batch')))

    def failures(self):
        with self.assertRaises(SilverContractError) as caught:
            validate_silver_frames(self.frames, self.plan)
        report = caught.exception.report
        self.assertEqual(report['accepted_rows'], 0)
        return {c['check']: c for c in report['checks'] if not c['success']}

    def test_hand_calculated_cardinalities_and_temporal_diagnostic(self):
        r = validate_silver_frames(self.frames, self.plan, {name: 3 for name in self.frames})
        self.assertEqual(r['accepted_rows'], 9)
        relation = r['relationships']['previous_applications']
        self.assertEqual((relation['orphan_keys'], relation['parent_keys_without_match'], relation['max_rows_per_covered_case']), (0, 1, 2))
        self.assertEqual((relation['child_left_join_rows'], relation['base_left_join_rows']), (3, 4))
        self.assertEqual(relation['auxiliary_dates_after_decision'], {'observedD': 1})
        self.assertEqual(r['relationships']['credit_static']['auxiliary_dates_after_decision'], {'offerD': 1})
        self.assertEqual(r['tables']['credit_static']['null_counts']['amount'], 1)

    def test_empty_optional_history_passes_but_missing_dataset_blocks(self):
        self.frames['previous_applications'] = self.frames['previous_applications'].limit(0)
        r = validate_silver_frames(self.frames, self.plan)
        self.assertEqual(r['accepted_rows'], 6)
        self.assertEqual(r['relationships']['previous_applications']['parent_keys_without_match'], 3)
        del self.frames['previous_applications']
        self.assertIn('dataset_present', self.failures())

    def test_composite_duplicate_and_null_key_block(self):
        from pyspark.sql import functions as F
        original = self.frames['previous_applications']
        self.frames['previous_applications'] = original.unionByName(original.limit(1))
        self.assertIn('unique_key', self.failures())
        self.frames['previous_applications'] = original.withColumn('num_group1', F.lit(None).cast('long'))
        self.assertIn('required_non_null', self.failures())

    def test_orphan_and_incomplete_static_coverage_block(self):
        from pyspark.sql import functions as F
        self.frames['credit_static'] = self.frames['credit_static'].filter('case_id != 3')
        self.frames['previous_applications'] = self.frames['previous_applications'].withColumn('case_id', F.lit(9).cast('long'))
        failed = self.failures()
        self.assertIn('foreign_key', failed)
        self.assertIn('full_parent_coverage', failed)

    def test_date_type_drift_and_extra_column_block_without_cast(self):
        from pyspark.sql import functions as F
        original = self.frames['credit_static']
        self.frames['credit_static'] = original.withColumn('offerD', F.col('offerD').cast('string'))
        self.assertIn('exact_schema', self.failures())
        self.frames['credit_static'] = original.withColumn('extra', F.lit(1))
        self.assertIn('exact_schema', self.failures())

    def test_domains_calendar_and_blank_metadata_block(self):
        from pyspark.sql import functions as F
        self.frames['credit_cases'] = (self.frames['credit_cases'].withColumn('target', F.lit(2).cast('long'))
            .withColumn('WEEK_NUM', F.lit(-1).cast('long')).withColumn('MONTH', F.lit(202002).cast('long')))
        self.frames['previous_applications'] = self.frames['previous_applications'].withColumn('num_group1', F.lit(-1).cast('long'))
        self.frames['credit_static'] = self.frames['credit_static'].withColumn('_source_file', F.lit('  '))
        self.assertTrue({'target_domain', 'non_negative_week', 'month_matches_decision',
                         'non_negative_group_index', 'non_blank_metadata'} <= set(self.failures()))

    def test_row_count_drift_blocks_even_when_data_remains_valid(self):
        with self.assertRaises(SilverContractError) as caught:
            validate_silver_frames(self.frames, self.plan,
                {'credit_cases': 3, 'credit_static': 3, 'previous_applications': 4})
        failed = [c['check'] for c in caught.exception.report['checks'] if not c['success']]
        self.assertEqual(failed, ['selection_row_count'])
