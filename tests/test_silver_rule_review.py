from pathlib import Path
import unittest

from src.profiling.inspect_silver_candidates import profile_candidates

ROOT = Path(__file__).resolve().parents[1]


class SilverRuleReviewSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='silver-rule-review-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_numeric_probe_is_counted_without_changing_values(self):
        df = self.spark.createDataFrame([(1, 99.0), (2, -1.0), (3, 1.5), (4, 2**31 * 1.0), (5, None)],
                                         'case_id long, amount double')
        original = df.collect()
        p = profile_candidates(df, dict(df.dtypes), ['case_id'], [])['columns']['amount']
        self.assertEqual((p['probe_99'], p['probe_-1'], p['fractional'], p['outside_int32'], p['nulls']), (1, 1, 1, 1, 1))
        self.assertEqual(df.collect(), original)

    def test_empty_input_has_defined_counts_and_no_fake_range(self):
        df = self.spark.createDataFrame([], 'case_id long, value double, exampleD string')
        p = profile_candidates(df, dict(df.dtypes), ['case_id'], [])
        self.assertEqual(p['rows'], 0)
        self.assertEqual(p['columns']['value']['nulls'], 0)
        self.assertIsNone(p['columns']['value']['min'])
        self.assertEqual(p['columns']['exampleD']['invalid_date'], 0)

    def test_null_constant_date_and_code_patterns_are_separate_metrics(self):
        df = self.spark.createDataFrame([
            (1, '2020-02-30', 'a55475b1', False, 'x'),
            (2, '2020-01-01', 'Q3_9_meet', True, None),
            (3, None, 'P1_2_3', None, 'x')],
            'case_id long, exampleD string, codeM string, flag boolean, constant string')
        p = profile_candidates(df, dict(df.dtypes), ['case_id'], ['constant'])['columns']
        self.assertEqual(p['exampleD']['invalid_date'], 1)
        self.assertEqual(p['codeM']['hex_format'], 1)
        self.assertEqual(p['codeM']['q_format'], 1)
        self.assertEqual(p['codeM']['p_format'], 1)
        self.assertEqual(p['flag'], {'nulls': 1, 'false': 1, 'true': 1})
        self.assertEqual(p['constant']['exact_distinct_non_null'], 1)
        self.assertEqual(p['constant']['nulls'], 1)
