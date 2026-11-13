"""F06: oráculos pequenos, atualização auxiliar, falhas e versões históricas reais."""
from datetime import date
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from publication_fixture import fixture_frames
from src.gold.model import build_abt, build_monthly, load_gold_contract, affected_cases
from src.gold.publish import publish_analytics
from src.gold.quality import GoldQualityError, validate_abt, validate_monthly
from src.pipelines.download_home_credit import sha256
from src.publication.evolution import prepare_silver
from src.publication.protocol import (InjectedFailure, activate_publication, current_id, fail_at,
    open_publication, publish_snapshot, verify_manifest)
from src.utils.run_context import RunContext


class GoldIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='f06-integration', delta=True)
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions', '2')
        cls.temp = tempfile.TemporaryDirectory()
        cls.template = Path(cls.temp.name) / 'template'
        cls.template.mkdir()
        (cls.template / 'fixture.json').write_text('{"kind":"synthetic_fixture_only"}\n')
        cls.fingerprints = {'fixture.json': sha256(cls.template / 'fixture.json')}
        cls.spec = load_gold_contract(ROOT / 'configs/contracts/gold_v1.yaml',
                                     ROOT / 'configs/contracts/silver_managed_v2.yaml')
        cls.sources = {}
        cls.raw = {}
        registry = cls.template / 'artifacts/publications/silver'
        for label, kwargs in [('baseline', {}), ('corrected', {'corrected': True}),
                              ('late', {'corrected': True, 'late': True}),
                              ('history_only', {'history_only': True})]:
            frames, cls.plan = fixture_frames(cls.spark, **kwargs)
            cls.raw[label] = frames
            counts = {name: frame.count() for name, frame in frames.items()}
            identity = {'scope': 'silver_v2', 'selection_id': 'a' * 24, 'snapshot': label}
            cls.sources[label], _ = publish_snapshot(RunContext.create(cls.template), registry, cls.spark,
                identity, cls.fingerprints, lambda tx: prepare_silver(tx, frames, cls.plan, counts))
        cls.baseline, _ = publish_analytics(RunContext.create(cls.template), cls.spark,
            cls.template / 'artifacts/publications/analytics', source_registry=registry,
            source_manifest=cls.sources['baseline'], plan=cls.plan, spec=cls.spec,
            fingerprints=cls.fingerprints)

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.repo = Path(self.temp.name) / self._testMethodName
        shutil.copytree(self.template, self.repo)
        self.registry = self.repo / 'artifacts/publications/analytics'
        self.source_registry = self.repo / 'artifacts/publications/silver'

    def publish(self, label, *, parent='baseline', hook=None):
        if parent == 'baseline':
            parent = {'manifest': self.baseline}
        return publish_analytics(RunContext.create(self.repo), self.spark, self.registry,
            source_registry=self.source_registry, source_manifest=self.sources[label], plan=self.plan,
            spec=self.spec, fingerprints=self.fingerprints, parent=parent, hook=hook)

    def test_hand_oracle_history_aggregation_preserves_case_grain(self):
        with open_publication(self.repo, self.registry, self.spark) as (_, frames):
            rows = {r.case_id: r for r in frames['gold.abt'].collect()}
            self.assertEqual(len(rows), 3)
            self.assertEqual((rows[1].previous_application_count, rows[1].previous_amount_non_null_count), (2, 1))
            self.assertEqual((rows[1].previous_amount_sum, rows[1].previous_amount_mean), (5.0, 5.0))
            self.assertIsNone(rows[2].static_annuity)
            self.assertTrue(rows[2].has_static)
            self.assertFalse(rows[3].has_previous_applications)
            self.assertEqual(rows[3].previous_application_count, 0)
            self.assertIsNone(rows[3].previous_amount_sum)
            months = {r.MONTH: r for r in frames['gold.monthly_metrics'].collect()}
            self.assertEqual(months[202001].target_1_rate, 0.5)
            self.assertEqual(months[202002].history_coverage_rate, 0.0)

    def test_null_amounts_missing_static_null_labels_and_empty_population(self):
        from pyspark.sql import functions as F
        frames = dict(self.raw['baseline'])
        frames['credit_cases'] = frames['credit_cases'].withColumn('target', F.lit(None).cast('long'))
        frames['credit_static'] = frames['credit_static'].filter('case_id != 3')
        frames['previous_applications'] = frames['previous_applications'].withColumn('credamount_590A', F.lit(None).cast('double'))
        abt = build_abt(frames)
        row = abt.filter('case_id=1').first()
        self.assertEqual(row.previous_application_count, 2)
        self.assertEqual(row.previous_amount_non_null_count, 0)
        self.assertIsNone(row.previous_amount_sum)
        self.assertIsNone(row.previous_amount_mean)
        self.assertFalse(abt.filter('case_id=3').first().has_static)
        monthly = build_monthly(abt)
        self.assertTrue(all(r.valid_label_count == 0 and r.target_1_rate is None for r in monthly.collect()))
        validate_abt(abt, frames, self.spec)
        validate_monthly(monthly, abt, frames, self.spec)
        empty = {n: f.limit(0) for n, f in frames.items()}
        self.assertEqual(build_monthly(build_abt(empty)).count(), 0)

    def test_auxiliary_corrections_and_late_case(self):
        corrected, _ = self.publish('corrected')
        self.assertEqual(corrected['details']['gold_update']['affected_cases'], 1)
        self.assertEqual(corrected['details']['gold_update']['updates'], 1)
        late, _ = self.publish('late', parent={'manifest': corrected})
        self.assertEqual(late['details']['gold_update']['inserts'], 1)
        self.assertEqual(late['details']['gold_update']['updates'], 0)
        with open_publication(self.repo, self.registry, self.spark) as (_, frames):
            self.assertEqual(frames['gold.abt'].count(), 4)
            one = frames['gold.abt'].filter('case_id=1').first()
            self.assertEqual((one.static_annuity, one.previous_amount_sum), (11.0, 6.0))
            jan = frames['gold.monthly_metrics'].filter('MONTH=202001').first()
            self.assertEqual(jan.case_count, 3)
            self.assertEqual(jan.target_1_rate, 1 / 3)
        self.assertTrue(late['validations']['abt_full_recomputation']['success'])

    def test_history_only_change_reaches_abt(self):
        manifest, _ = self.publish('history_only')
        self.assertEqual(manifest['details']['gold_update']['affected_cases'], 1)
        with open_publication(self.repo, self.registry, self.spark) as (_, frames):
            row = frames['gold.abt'].filter('case_id=1').first()
            self.assertEqual(row.static_annuity, 10.0)
            self.assertEqual(row.previous_amount_sum, 6.0)
            self.assertTrue(row.has_revised_source)

    def test_failure_between_silver_and_gold_keeps_approved_pair(self):
        with self.assertRaises(InjectedFailure):
            self.publish('corrected', hook=fail_at('between_silver_and_gold'))
        self.assertEqual(current_id(self.registry), self.baseline['publication_id'])
        manifest, _ = self.publish('corrected')
        self.assertEqual(current_id(self.registry), manifest['publication_id'])
        self.assertEqual(set(manifest['tables']), {'silver.' + n for n in self.plan['tables']} | {'gold.abt', 'gold.monthly_metrics'})

    def test_post_merge_failure_resumes_without_second_merge(self):
        with self.assertRaises(InjectedFailure):
            self.publish('corrected', hook=fail_at('after_commit:gold.abt:merge'))
        self.assertEqual(current_id(self.registry), self.baseline['publication_id'])
        manifest, _ = self.publish('corrected')
        update = manifest['details']['gold_update']
        self.assertEqual(update['updates'], 1)
        self.assertEqual(update['commits_this_attempt'], {'inserts': 0, 'updates': 0})
        self.assertEqual(manifest['tables']['gold.abt']['version'], 1)
        repeated, retry = self.publish('corrected')
        self.assertTrue(retry['reused'])
        self.assertEqual(manifest, repeated)

    def test_real_bad_gold_quality_cannot_publish(self):
        # A duplicação atravessa a gravação Delta; o contrato/oráculo independente bloqueia CURRENT.
        with patch('src.gold.publish.build_abt', side_effect=lambda silver: build_abt(silver).unionByName(build_abt(silver))):
            with self.assertRaises(GoldQualityError):
                self.publish('corrected', parent=None)
        self.assertEqual(current_id(self.registry), self.baseline['publication_id'])
        with self.assertRaises(InjectedFailure):
            self.publish('history_only', hook=fail_at('after_gold_quality'))
        self.assertEqual(current_id(self.registry), self.baseline['publication_id'])
        self.publish('history_only')

    def test_month_move_removes_empty_period_and_rollback_restores_pair(self):
        from pyspark.sql import functions as F
        frames = dict(self.raw['baseline'])
        frames['credit_cases'] = (frames['credit_cases']
            .withColumn('MONTH', F.lit(202001).cast('long'))
            .withColumn('date_decision', F.when(F.col('case_id') == 3, F.lit(date(2020, 1, 3))).otherwise(F.col('date_decision')))
            .withColumn('_source_revision', F.when(F.col('case_id') == 3, 2).otherwise(1).cast('long')))
        counts = {n: f.count() for n, f in frames.items()}
        source, _ = publish_snapshot(RunContext.create(self.repo), self.source_registry, self.spark,
            {'scope': 'silver_v2', 'selection_id': 'a' * 24, 'snapshot': 'moved_month'}, self.fingerprints,
            lambda tx: prepare_silver(tx, frames, self.plan, counts))
        manifest, _ = publish_analytics(RunContext.create(self.repo), self.spark, self.registry,
            source_registry=self.source_registry, source_manifest=source, plan=self.plan, spec=self.spec,
            fingerprints=self.fingerprints, parent={'manifest': self.baseline})
        self.assertEqual(manifest['details']['gold_update']['affected_months'], [202001, 202002])
        with open_publication(self.repo, self.registry, self.spark) as (_, current):
            rows = current['gold.monthly_metrics'].collect()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].target_1_rate, 2 / 3)
        activate_publication(self.repo, self.registry, self.spark, self.baseline['publication_id'], 'fixture_rollback')
        with open_publication(self.repo, self.registry, self.spark) as (old, frames):
            self.assertEqual(old['publication_id'], self.baseline['publication_id'])
            self.assertEqual(frames['gold.monthly_metrics'].count(), 2)
            self.assertEqual(frames['gold.abt'].filter('case_id=3').first().MONTH, 202002)
        with self.assertRaises(ValueError):
            affected_cases(self.raw['baseline'], {**self.raw['baseline'],
                'credit_cases': self.raw['baseline']['credit_cases'].filter('case_id != 3')})


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GoldIntegrationTests))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
