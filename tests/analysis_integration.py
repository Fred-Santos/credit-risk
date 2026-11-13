"""F07: oráculos manuais, nulos, corrupção de indicadores e comparação de populações."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from publication_fixture import fixture_frames
from src.analytics.queries import (load_analysis_policy,monthly_analysis,population_summary,
    history_segments,compare_publications)
from src.gold.model import build_abt,build_monthly
from src.pipelines.run_analysis import collect_view


class AnalysisIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark=create_spark_session(ROOT,app_name='f07-integration')
        cls.policy=load_analysis_policy(ROOT/'configs/analysis_policy_v1.yaml')
        cls.frames={}
        for label,kwargs in [('baseline',{}),('corrected',{'corrected':True}),
                             ('final',{'corrected':True,'late':True})]:
            silver,_=fixture_frames(cls.spark,**kwargs)
            abt=build_abt(silver).cache()
            abt.count()
            cls.frames[label]={'gold.abt':abt,'gold.monthly_metrics':build_monthly(abt)}

    @classmethod
    def tearDownClass(cls):
        for frame in cls.frames.values():
            frame['gold.abt'].unpersist()
        cls.spark.stop()

    def test_hand_counts_denominators_coverage_and_completeness(self):
        view=collect_view(self.frames['baseline'],self.policy)
        p=view['population']
        self.assertEqual((p['case_count'],p['target_1_count'],p['valid_label_count']),(3,2,3))
        self.assertEqual(p['target_1_rate'],2/3)
        self.assertEqual(p['static_covered_count'],3)
        self.assertEqual(p['static_annuity_non_null_count'],2)
        self.assertEqual(p['history_covered_count'],2)
        self.assertEqual(p['history_row_count'],3)
        self.assertEqual(p['history_amount_completeness'],2/3)
        self.assertEqual(view['monthly'][0]['target_1_rate'],.5)
        self.assertEqual(view['monthly'][0]['history_coverage_rate'],1)
        segments={r['segment']:r for r in view['segments']}
        self.assertEqual(segments['no_history']['case_count'],1)
        self.assertEqual(segments['two_to_five']['case_count'],1)
        self.assertTrue(segments['six_or_more']['empty_group'])
        self.assertIsNone(segments['six_or_more']['target_1_rate'])

    def test_null_labels_and_empty_population_do_not_invent_zero_rates(self):
        from pyspark.sql import functions as F
        abt=self.frames['baseline']['gold.abt'].withColumn('target',F.lit(None).cast('long'))
        p=population_summary(abt)
        self.assertEqual(p['missing_label_count'],3)
        self.assertIsNone(p['target_1_rate'])
        monthly,_=monthly_analysis(abt,build_monthly(abt),self.policy)
        self.assertTrue(all(r['target_1_rate'] is None for r in monthly))
        empty=abt.limit(0)
        self.assertEqual(monthly_analysis(empty,build_monthly(empty),self.policy)[0],[])
        self.assertIsNone(population_summary(empty)['target_1_rate'])
        self.assertTrue(all(r['empty_group'] for r in history_segments(empty,self.policy)[0]))

    def test_corrupted_published_indicator_is_blocked(self):
        from pyspark.sql import functions as F
        frames=self.frames['baseline']
        corrupt=frames['gold.monthly_metrics'].withColumn('target_1_count',F.col('target_1_count')+1)
        with self.assertRaisesRegex(ValueError,'divergem'):
            monthly_analysis(frames['gold.abt'],corrupt,self.policy)

    def test_auxiliary_correction_changes_values_without_population_or_rate_change(self):
        result=compare_publications(self.frames['baseline'],self.frames['corrected'],kind='correction',policy=self.policy)
        self.assertEqual(result['changed_common_cases'],1)
        self.assertEqual(result['added_cases'],0)
        self.assertTrue(result['monthly_unchanged'])
        changed=result['changed_cases'][0]
        self.assertEqual(changed['case_id'],1)
        self.assertEqual(changed['columns']['static_annuity'],{'before':10.0,'after':11.0})
        self.assertEqual(changed['columns']['previous_amount_sum'],{'before':5.0,'after':6.0})

    def test_late_population_is_compared_separately(self):
        result=compare_publications(self.frames['corrected'],self.frames['final'],kind='late_arrival',policy=self.policy)
        self.assertEqual((result['added_cases'],result['removed_cases'],result['changed_common_cases']),(1,0,0))
        change=result['monthly_changes'][0]
        self.assertEqual(change['MONTH'],202001)
        self.assertEqual(change['before']['target_1_rate'],.5)
        self.assertEqual(change['after']['target_1_rate'],1/3)
        with self.assertRaisesRegex(ValueError,'mesma população'):
            compare_publications(self.frames['baseline'],self.frames['final'],kind='correction',policy=self.policy)

    def test_changed_labels_and_duplicate_grain_block_analysis(self):
        from pyspark.sql import functions as F
        baseline=self.frames['baseline']
        changed={**baseline,'gold.abt':baseline['gold.abt'].withColumn('target',F.lit(0).cast('long'))}
        with self.assertRaisesRegex(ValueError,'rótulo'):
            compare_publications(baseline,changed,kind='correction',policy=self.policy)
        with self.assertRaisesRegex(ValueError,'grão'):
            population_summary(baseline['gold.abt'].unionByName(baseline['gold.abt']))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AnalysisIntegrationTests))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
