"""F05: migração Delta, visibilidade, falhas/retomada e retenção em JVM própria."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from publication_fixture import fixture_frames
from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.publication.evolution import MARKER, prepare_silver, validate_sources
from src.publication.protocol import (InjectedFailure, NoPublicationError, activate_publication, current_id,
    fail_at, open_publication, publish_snapshot, verify_manifest)
from src.publication.retention import audit_retention, retention_fixture
from src.quality.event_contracts import digest
from src.quality.silver_contracts import SilverContractError
from src.utils.run_context import RunContext


class PublicationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='f05-integration', delta=True)
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions', '2')
        cls.temp = tempfile.TemporaryDirectory()
        cls.template = Path(cls.temp.name) / 'template'
        cls.template.mkdir()
        (cls.template / 'fixture.json').write_text('{"kind":"synthetic_fixture_only"}\n')
        cls.base, cls.plan = fixture_frames(cls.spark)
        cls.corrected, _ = fixture_frames(cls.spark, corrected=True)
        cls.fingerprints = {'fixture.json': sha256(cls.template / 'fixture.json')}
        ctx = RunContext.create(cls.template)
        registry = cls.template / 'artifacts/publications/silver'
        identity = {'scope': 'silver_v2', 'selection_id': 'a' * 24, 'snapshot': 'baseline'}
        counts = {'credit_cases': 3, 'credit_static': 3, 'previous_applications': 3}
        cls.baseline, _ = publish_snapshot(ctx, registry, cls.spark, identity, cls.fingerprints,
            lambda tx: prepare_silver(tx, cls.base, cls.plan, counts))

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.repo = Path(self.temp.name) / self._testMethodName
        shutil.copytree(self.template, self.repo)
        self.registry = self.repo / 'artifacts/publications/silver'
        self.counts = {'credit_cases': 3, 'credit_static': 3, 'previous_applications': 3}

    def identity(self, label):
        return {'scope': 'silver_v2', 'selection_id': 'a' * 24, 'snapshot': label}

    def publish(self, label, *, frames=None, hook=None):
        data = self.corrected if frames is None else frames
        validate_sources(data, self.plan)
        return publish_snapshot(RunContext.create(self.repo), self.registry, self.spark,
            self.identity(label), self.fingerprints, lambda tx: prepare_silver(tx, data, self.plan, self.counts), hook=hook)

    def test_initial_read_and_authorized_migration(self):
        empty = self.repo / 'empty_registry'
        with self.assertRaises(NoPublicationError):
            with open_publication(self.repo, empty, self.spark):
                pass
        with open_publication(self.repo, self.registry, self.spark) as (manifest, frames):
            self.assertEqual(manifest['publication_id'], self.baseline['publication_id'])
            for name, frame in frames.items():
                self.assertEqual(dict(frame.dtypes)[MARKER], 'int')
                self.assertEqual({r[0] for r in frame.select(MARKER).distinct().collect()}, {2})
                self.assertEqual(manifest['tables'][name]['version'], 2)
                path = self.repo / manifest['tables'][name]['path']
                old = self.spark.read.format('delta').option('versionAsOf', 0).load(str(path))
                self.assertNotIn(MARKER, old.columns)

    def test_schema_drift_blocks_before_writes(self):
        from pyspark.sql import functions as F
        before = current_id(self.registry)
        source = self.base['credit_cases']
        for bad in (source.drop('case_id'), source.withColumn('target', F.col('target').cast('string')),
                    source.withColumn('extra', F.lit(1))):
            with self.assertRaises(ValueError):
                self.publish('bad_schema', frames={**self.base, 'credit_cases': bad})
        self.assertEqual(current_id(self.registry), before)
        self.assertFalse((self.registry / 'manifests' / (digest(self.identity('bad_schema'))[:24] + '.json')).exists())

    def test_before_after_commit_and_between_tables_resume(self):
        points = ['before_commit:silver.credit_cases:create', 'after_commit:silver.credit_cases:create',
                  'after_migration:credit_static']
        for i, point in enumerate(points):
            label = 'failure_' + str(i)
            before = current_id(self.registry)
            with self.assertRaises(InjectedFailure):
                self.publish(label, hook=fail_at(point))
            self.assertEqual(current_id(self.registry), before)
            manifest, _ = self.publish(label)
            self.assertEqual(current_id(self.registry), manifest['publication_id'])
            self.assertEqual({e['version'] for e in manifest['tables'].values()}, {2})
            self.assertEqual(manifest['validations']['silver_contracts']['accepted_rows'], 9)

    def test_failed_quality_preserves_previous_publication(self):
        from pyspark.sql import functions as F
        before = current_id(self.registry)
        bad = {**self.base, 'credit_cases': self.base['credit_cases'].withColumn('target', F.lit(7).cast('long'))}
        with self.assertRaises(SilverContractError):
            self.publish('bad_quality', frames=bad)
        self.assertEqual(current_id(self.registry), before)
        with self.assertRaises(InjectedFailure):
            self.publish('after_quality', hook=fail_at('after_silver_quality'))
        self.assertEqual(current_id(self.registry), before)

    def test_manifest_and_pointer_crash_windows(self):
        previous = current_id(self.registry)
        with self.assertRaises(InjectedFailure):
            self.publish('manifest_exists', hook=fail_at('before_pointer'))
        self.assertEqual(current_id(self.registry), previous)
        manifest, retry = self.publish('manifest_exists')
        self.assertTrue(retry['reused'])
        with self.assertRaises(InjectedFailure):
            self.publish('pointer_committed', hook=fail_at('after_pointer'))
        committed = digest(self.identity('pointer_committed'))[:24]
        self.assertEqual(current_id(self.registry), committed)
        _, retry = self.publish('pointer_committed')
        self.assertTrue(retry['reused'])
        self.assertTrue(retry['activation']['reused'])

    def test_single_writer_and_reader_lock(self):
        with _ingestion_lock(self.registry, '.publication.lock'):
            with self.assertRaises(OSError):
                self.publish('concurrent_writer')
        with open_publication(self.repo, self.registry, self.spark):
            with self.assertRaises(OSError):
                self.publish('writer_during_read')
        self.assertEqual(current_id(self.registry), self.baseline['publication_id'])

    def test_rollback_reproduces_approved_snapshot(self):
        latest, _ = self.publish('corrected')
        activate_publication(self.repo, self.registry, self.spark, self.baseline['publication_id'], 'rollback_fixture')
        with open_publication(self.repo, self.registry, self.spark) as (manifest, frames):
            amount = frames['silver.credit_static'].filter('case_id = 1').first().annuity_780A
            self.assertEqual(amount, 10.0)
        activate_publication(self.repo, self.registry, self.spark, latest['publication_id'], 'restore_fixture')
        with open_publication(self.repo, self.registry, self.spark) as (_, frames):
            self.assertEqual(frames['silver.credit_static'].filter('case_id = 1').first().annuity_780A, 11.0)

    def test_corruption_unknown_directory_and_owned_orphan(self):
        manifest_path = self.registry / 'manifests' / (self.baseline['publication_id'] + '.json')
        original = manifest_path.read_bytes()
        value = json.loads(original)
        value['status'] = 'failed'
        manifest_path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify_manifest(self.repo, self.registry, self.baseline['publication_id'], self.spark)
        manifest_path.write_bytes(original)
        ctx = RunContext.create(self.repo)
        unknown_id = digest(self.identity('unknown'))[:24]
        unknown = ctx.silver_dir / 'samples' / ('a' * 24) / 'published' / unknown_id / 'credit_cases'
        unknown.mkdir(parents=True)
        marker = unknown / 'keep.txt'
        marker.write_text('preserve')
        with self.assertRaises(ValueError):
            self.publish('unknown')
        self.assertEqual(marker.read_text(), 'preserve')
        orphan_id = digest(self.identity('owned_orphan'))[:24]
        orphan = ctx.silver_dir / 'samples' / ('a' * 24) / 'published' / orphan_id / 'credit_cases'

        def interrupt_before_delta(stage):
            if stage == 'before_commit:silver.credit_cases:create':
                orphan.mkdir(parents=True)
                (orphan / 'uncommitted.parquet').write_bytes(b'synthetic uncommitted bytes')
                raise InjectedFailure('owned fixture interrupted before Delta commit')

        with self.assertRaises(InjectedFailure):
            self.publish('owned_orphan', hook=interrupt_before_delta)
        resumed, _ = self.publish('owned_orphan')
        self.assertFalse((orphan / 'uncommitted.parquet').exists())
        file = next((self.repo / resumed['tables']['silver.credit_static']['path']).glob('*.parquet'))
        file.unlink()
        with self.assertRaises(ValueError):
            verify_manifest(self.repo, self.registry, resumed['publication_id'], self.spark)

    def test_retention_preserves_pins_and_vacuum_is_fixture_only(self):
        audit = audit_retention(self.repo, self.registry, self.spark)
        self.assertEqual(audit['status'], 'passed')
        result = retention_fixture(self.spark)
        self.assertTrue(result['forced_fixture_vacuum_loses_old_data'])
        self.assertFalse(result['real_data_cleaned'])
        verify_manifest(self.repo, self.registry, self.baseline['publication_id'], self.spark)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicationIntegrationTests))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
