import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from src.utils.spark import create_spark_session
from src.expansion.analysis import build_analysis,verify_analysis
from expansion_delivery_fixture import fixture


class DeliveryAnalysisTests(unittest.TestCase):
    def test_nine_months_denominators_missingness_and_sentinel_codes(self):
        spark=create_spark_session(ROOT,app_name='delivery-fixture',delta=True)
        spark.conf.set('spark.databricks.delta.snapshotPartitions','2')
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo=Path(tmp);silver,gold,policy=fixture(repo,spark)
                manifest,reused=build_analysis(repo,spark,silver,gold,policy,render=False)
                self.assertFalse(reused)
                result=repo/'data/gold/expansion-analysis'/manifest['id']
                report=json.loads((result/'report/report.json').read_text())
                self.assertEqual(len(report['rows']['monthly']),9)
                self.assertEqual(report['population_cases'],3)
                self.assertEqual(sum(r['empty_month'] for r in report['rows']['monthly']),7)
                self.assertEqual(len(report['rows']['coverage']),9)
                jan=report['rows']['monthly'][0];self.assertEqual((jan['case_count'],jan['target_1_count']),(2,1))
                self.assertEqual(jan['target_1_rate'],.5)
                categories={r['category'] for r in report['rows']['composition'] if r['dimension']=='product_code' and r['MONTH']==202001}
                self.assertEqual(categories,{'__NULL__','VALUE:__NULL__'})
                self.assertTrue(build_analysis(repo,spark,silver,gold,policy,render=False)[1])
                (result/'report/monthly.csv').write_text('corrupt')
                with self.assertRaises(ValueError):verify_analysis(result)
        finally:spark.stop()


if __name__=='__main__':unittest.main(verbosity=2)
