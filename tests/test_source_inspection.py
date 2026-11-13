import importlib.util
from pathlib import Path
import unittest

from src.profiling.inspect_home_credit import profile_frame, profile_base


@unittest.skipUnless(importlib.util.find_spec('pyspark'), 'PySpark não instalado')
class SourceInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(Path(__file__).resolve().parents[1], app_name='inspection-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_grain_nulls_duplicates_and_nan(self):
        frame = self.spark.createDataFrame(
            [(101, 0, 1.0), (101, 1, float('nan')), (101, 1, None), (None, 0, 4.0)],
            'case_id long, num_group1 long, amount double')
        result = profile_frame(frame, ['case_id', 'num_group1'])
        self.assertEqual(result['rows'], 4)
        self.assertEqual(result['distinct_cases'], 1)
        self.assertEqual(result['null_key_rows'], 1)
        self.assertEqual(result['duplicate_key_groups'], 1)
        self.assertEqual(result['duplicate_excess_rows'], 1)
        amount = next(field for field in result['schema'] if field['column'] == 'amount')
        self.assertEqual((amount['null_count'], amount['nan_count']), (1, 1))

    def test_base_flags_invalid_dates_months_and_targets(self):
        frame = self.spark.createDataFrame(
            [(101, '2020-02-30', 202002, 1, 2), (102, '2020-03-01', 202004, 2, 0)],
            'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long')
        result = profile_base(frame)
        self.assertEqual(result['invalid_dates'], 1)
        self.assertEqual(result['month_mismatches'], 1)
        self.assertEqual(result['invalid_targets'], 1)
