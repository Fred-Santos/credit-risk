"""F04 em JVM Delta própria; fixtures sintéticas, sem credenciais Home Credit."""
from datetime import date
from functools import reduce
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bronze.event_parquet import (encode_events, publish_packet, read_packets,
    revision_index, validate_transport)
from src.pipelines.run_incremental_demo import generate_demo, load_incremental_policy, with_ordinals
from src.quality.bronze_contract import METADATA
from src.quality.event_contracts import EventConflictError, make_event
from src.quality.reconcile_bronze import compare_rows
from src.quality.silver_contracts import DOMAINS, RELATIONSHIPS
from src.silver.incremental import (apply_packet, deduplicate, diagnostics, read_state,
    reconcile_state, reconstruct, transform_candidates, verify_state, initialize_state)
from src.silver.initial_delta import TABLES


class IncrementalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        from pyspark.sql import functions as F
        cls.spark = create_spark_session(ROOT, app_name='f04-integration', delta=True)
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions', '2')
        cls.temp = tempfile.TemporaryDirectory()
        cls.seed = Path(cls.temp.name) / 'seed'
        cls.selection = 'a' * 24
        cls.stream = 'f04_fixture'
        cls.binding = {'selection_id': cls.selection, 'fixture': 'f04_v1'}
        cls.identity = {'binding': cls.binding, 'stream_id': cls.stream}
        cls.contract = yaml.safe_load((ROOT / 'configs/contracts/home_credit_events_v1.yaml').read_text())
        cls.incremental_policy = load_incremental_policy(ROOT / 'configs/incremental_policy_v1.yaml')
        definitions = {
            'train_base': ([(1, '2020-01-01', 202001, 0, 0), (2, '2020-01-02', 202001, 1, 1),
                            (3, '2020-02-01', 202002, 60, 1), (4, '2020-03-01', 202003, 80, 0)],
                          'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long'),
            'train_static_0': ([(1, 10.0, 'ação', True), (2, 20.0, None, None),
                                (3, None, 'X_9', False), (4, 40.0, 'z', True)],
                              'case_id long, annuity_780A double, codeM string, flag boolean'),
            'train_applprev_1': ([(1, 0, 5.0, '2019-01-01'), (1, 1, None, None),
                                  (2, 0, 7.0, '2020-01-03'), (4, 0, 8.0, '2019-12-31')],
                                'case_id long, num_group1 long, credamount_590A double, observedD string')}
        cls.bronze, cls.snapshot, cls.policy, cls.plan = {}, {'tables': {}}, {'tables': {}}, {'domains': DOMAINS, 'tables': {}}
        for name, (rows, schema) in definitions.items():
            frame = cls.spark.createDataFrame(rows, schema)
            business_schema = dict(frame.dtypes)
            key = ['case_id', 'num_group1'] if name == 'train_applprev_1' else ['case_id']
            dates = ['date_decision'] if name == 'train_base' else ['observedD'] if name == 'train_applprev_1' else []
            required = list(business_schema) if name == 'train_base' else key
            cls.snapshot['tables'][name] = {'schema': business_schema, 'key': key,
                'required_non_null': required, 'minimum_rows': 0 if name == 'train_applprev_1' else 1}
            cls.policy['tables'][name] = {'key': key, 'cast_to_date': dates}
            target = TABLES[name]
            cls.plan['tables'][target] = {'schema': {**{c: 'date' if c in dates else t for c, t in business_schema.items()}, **METADATA},
                'key': key, 'required_non_null': required + list(METADATA), 'grain': 'synthetic_fixture',
                'minimum_rows': 0 if name == 'train_applprev_1' else 1, 'dates': dates,
                'relationship': RELATIONSHIPS.get(target)}
            cls.bronze[name] = (frame.withColumn('_run_id', F.lit('fixture_bronze'))
                .withColumn('_source_file', F.lit('file:///synthetic_fixture.parquet'))
                .withColumn('_ingest_date', F.lit(date(2020, 1, 1)))
                .withColumn('ingest_batch', F.lit('fixture_batch')))
        cls.assignments = cls.spark.createDataFrame([
            (1, 'b00_w000_051'), (2, 'b00_w000_051'), (3, 'b01_w052_077'), (4, 'b02_w078_091')],
            'case_id long, _batch_id string')
        cls.batch_specs = yaml.safe_load((ROOT / 'configs/sample_policy.yaml').read_text())['batches']
        cls.events_seed = cls.seed / 'events' / cls.selection / cls.stream
        cls.generation = generate_demo(cls.events_seed, cls.spark, bronze=cls.bronze, assignments=cls.assignments,
            contract=cls.contract, snapshot=cls.snapshot, binding=cls.binding, policy=cls.incremental_policy,
            batch_specs=cls.batch_specs, run_id='fixture_generation')
        packets = read_packets(cls.events_seed, cls.spark, cls.snapshot, cls.binding)
        cls.state_seed = cls.seed / 'states' / cls.stream
        indices = [revision_index(f) for _, group in packets for f in group.values()]
        first_manifest, first_frames = packets[0]
        cls.initial = apply_packet(cls.state_seed, cls.spark, manifest=first_manifest, frames=first_frames,
            history_indices=indices, snapshot=cls.snapshot, policy=cls.policy, plan=cls.plan,
            identity=cls.identity, run_id='fixture_initial')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.work = Path(self.temp.name) / self._testMethodName
        self.events = self.work / 'events' / self.selection / self.stream
        self.state = self.work / 'states' / self.stream
        shutil.copytree(self.events_seed, self.events)
        shutil.copytree(self.state_seed, self.state)
        self.packets = read_packets(self.events, self.spark, self.snapshot, self.binding)
        self.history = {t: reduce(lambda a, b: a.unionByName(b), [f[t] for _, f in self.packets]) for t in TABLES}
        self.indices = [revision_index(f) for f in self.history.values()]

    def apply(self, batch):
        manifest, frames = next(p for p in self.packets if p[0]['batch_id'] == batch)
        return apply_packet(self.state, self.spark, manifest=manifest, frames=frames,
            history_indices=self.indices, snapshot=self.snapshot, policy=self.policy, plan=self.plan,
            identity=self.identity, run_id='fixture_retry')

    def encode(self, sources, batch, revision=1, scenario='late_arrival'):
        return {t: encode_events(with_ordinals(sources.get(t, self.bronze[t].limit(0)), self.snapshot['tables'][t]['key']),
            self.contract, self.snapshot, selection_id=self.selection, stream_id=self.stream, batch_id=batch,
            table=t, revision=revision, scenario=scenario, origin='synthetic_fixture') for t in TABLES}

    def publish(self, sources, batch, revision=1, scenario='late_arrival'):
        frames = self.encode(sources, batch, revision, scenario)
        return publish_packet(self.events, self.spark, frames=frames, contract=self.contract, snapshot=self.snapshot,
                              binding=self.binding, batch_id=batch, run_id='fixture_negative')

    def test_distributed_encoding_matches_reference_with_unicode_null_and_signed_zero(self):
        from pyspark.sql import functions as F
        table = 'train_static_0'
        source = self.bronze[table].filter('case_id = 1').withColumn('annuity_780A', F.lit(-0.0))
        encoded = self.encode({table: source}, 'encoding')[table]
        row = encoded.first().asDict()
        payload = {c: source.first()[c] for c in self.snapshot['tables'][table]['schema']}
        expected = make_event(self.contract, self.snapshot, selection_id=self.selection, stream_id=self.stream,
            batch_id='encoding', table=table, ordinal=0, source_revision=1, payload=payload,
            scenario='late_arrival', payload_origin='synthetic_fixture')
        self.assertEqual(row['_payload_sha256'], expected['_payload_sha256'])
        self.assertEqual(row['_event_id'], expected['_event_id'])
        self.assertEqual(row['_delivery_id'], expected['_delivery_id'])
        self.assertEqual(row['codeM'], 'ação')
        self.assertEqual(validate_transport(encoded, self.contract, self.snapshot,
            selection_id=self.selection, stream_id=self.stream, batch_id='encoding', table=table), 1)

    def test_generator_covers_baseline_and_withholds_late_case(self):
        self.assertTrue(all(p['success'] for p in self.generation['baseline_reconciliation'].values()))
        self.assertTrue(self.generation['old_revision_conflict_rejected'])
        self.assertEqual((self.generation['correction_case'], self.generation['late_case']), (1, 2))
        base_ids = {m['batch_id']: sorted(r.case_id for r in f['train_base'].select('case_id').collect())
                    for m, f in self.packets}
        self.assertEqual(base_ids['b00_w000_051'], [1])
        self.assertEqual(base_ids['b01_w052_077'], [3])
        self.assertEqual(base_ids['b02_w078_091'], [4])
        self.assertEqual(base_ids['late_case_r1'], [2])

    def test_merge_matches_hand_oracle_and_reconstruction(self):
        results = {m['batch_id']: self.apply(m['batch_id']) for m, _ in self.packets}
        frames = read_state(self.state, self.spark, self.plan)
        self.assertEqual(sorted((r.case_id, r.annuity_780A) for r in frames['credit_static'].collect()),
                         [(1, 11.0), (2, 20.0), (3, None), (4, 40.0)])
        self.assertEqual(sorted((r.case_id, r.num_group1, r.credamount_590A) for r in frames['previous_applications'].collect()),
                         [(1, 0, 6.0), (1, 1, None), (2, 0, 7.0), (4, 0, 8.0)])
        self.assertEqual(diagnostics(frames)['months'], [
            {'MONTH': 202001, 'cases': 2, 'target_1': 1}, {'MONTH': 202002, 'cases': 1, 'target_1': 1},
            {'MONTH': 202003, 'cases': 1, 'target_1': 0}])
        self.assertEqual(sum(s['updates'] for s in results['correction_r2']['metrics'].values()), 2)
        self.assertEqual(sum(s['duplicate_deliveries'] for s in results['duplicate_r2']['metrics'].values()), 2)
        self.assertEqual(sum(s['ignored_older_revision'] for s in results['old_revision_r1']['metrics'].values()), 2)
        self.assertEqual(results['late_case_r1']['metrics']['credit_cases']['inserts'], 1)
        for name in ('duplicate_r2', 'old_revision_r1'):
            self.assertEqual(results[name]['versions_before'], results[name]['versions_after'])
        self.assertEqual(reconcile_state(self.state, self.spark, self.history, self.snapshot, self.policy, self.plan)['status'], 'passed')

    def test_shuffled_deduplication_respects_composite_key_and_max_revision(self):
        from pyspark.sql import functions as F
        rebuilt = reconstruct(self.history, self.snapshot, self.policy)
        for table, events in self.history.items():
            shuffled = events.repartition(3).orderBy(F.rand(seed=11))
            chosen, stats = deduplicate(shuffled, self.snapshot, table)
            treated, _ = transform_candidates(chosen, self.snapshot, self.policy, table)
            self.assertTrue(compare_rows(rebuilt[TABLES[table]], treated, treated.columns)['success'])
            self.assertEqual(stats['input_deliveries'], stats['duplicate_deliveries'] + stats['superseded_revisions'] + stats['candidate_keys'])
        history = rebuilt['previous_applications']
        self.assertEqual(history.filter('case_id = 1').count(), 2)

    def test_old_revision_conflict_rejects_whole_packet_before_state_changes(self):
        from pyspark.sql import functions as F
        self.apply('correction_r2')
        before = verify_state(self.state, self.spark, self.plan, self.identity)
        changed = self.bronze['train_static_0'].filter('case_id = 1').withColumn('annuity_780A', F.lit(12.0))
        new = self.bronze['train_static_0'].filter('case_id = 1').withColumn('case_id', F.lit(5).cast('long'))
        with self.assertRaises(EventConflictError):
            self.publish({'train_static_0': changed.unionByName(new)}, 'conflict_old')
        self.assertFalse((self.events / 'conflict_old').exists())
        self.assertEqual(before, verify_state(self.state, self.spark, self.plan, self.identity))

    def test_same_batch_retry_preserves_receipt_values_and_versions(self):
        before = verify_state(self.state, self.spark, self.plan, self.identity)
        frames = read_state(self.state, self.spark, self.plan, version_map=before)
        receipt = self.state / 'applied/b00_w000_051.json'
        original = receipt.read_bytes()
        result = self.apply('b00_w000_051')
        self.assertTrue(result['reused_receipt'])
        self.assertEqual(before, result['versions_after'])
        self.assertEqual(receipt.read_bytes(), original)
        current = read_state(self.state, self.spark, self.plan)
        for name in frames:
            self.assertTrue(compare_rows(frames[name], current[name], frames[name].columns)['success'])
        manifest, packet = self.packets[0]
        retry = publish_packet(self.events, self.spark, frames={n: f.repartition(2) for n, f in packet.items()},
            contract=self.contract, snapshot=self.snapshot, binding=self.binding, batch_id=manifest['batch_id'], run_id='fixture_retry')
        self.assertTrue(retry['reused'])
        self.assertEqual(retry['first_run_id'], manifest['first_run_id'])

    def test_corrupt_packet_and_unbound_state_are_never_overwritten(self):
        file = next(self.events.rglob('*.parquet'))
        file.write_bytes(b'corrupt fixture')
        with self.assertRaises(ValueError):
            read_packets(self.events, self.spark, self.snapshot, self.binding)
        unknown = self.work / 'unbound'
        unknown.mkdir()
        marker = unknown / 'keep.txt'
        marker.write_text('preserve')
        with self.assertRaises((OSError, ValueError)):
            initialize_state(unknown, self.spark, identity=self.identity, plan=self.plan, run_id='fixture')
        self.assertEqual(marker.read_text(), 'preserve')

    def test_invalid_date_blocks_all_merges_before_any_commit(self):
        from pyspark.sql import functions as F
        from src.silver.transforms import SilverTransformError
        source = self.bronze['train_applprev_1'].filter('case_id = 4').withColumn('observedD', F.lit('2019-02-30'))
        self.publish({'train_applprev_1': source}, 'bad_date', revision=2)
        packets = read_packets(self.events, self.spark, self.snapshot, self.binding)
        manifest, frames = next(p for p in packets if p[0]['batch_id'] == 'bad_date')
        before = verify_state(self.state, self.spark, self.plan, self.identity)
        with self.assertRaises(SilverTransformError):
            apply_packet(self.state, self.spark, manifest=manifest, frames=frames, history_indices=self.indices,
                snapshot=self.snapshot, policy=self.policy, plan=self.plan, identity=self.identity, run_id='fixture_bad')
        self.assertEqual(before, verify_state(self.state, self.spark, self.plan, self.identity))
        self.assertFalse((self.state / 'applied/bad_date.json').exists())

    def test_auxiliary_only_correction_preserves_absent_siblings(self):
        before = read_state(self.state, self.spark, self.plan)
        counts = {n: f.count() for n, f in before.items()}
        result = self.apply('correction_r2')
        after = read_state(self.state, self.spark, self.plan)
        self.assertEqual({n: f.count() for n, f in after.items()}, counts)
        self.assertEqual(after['previous_applications'].filter('case_id=1 AND num_group1=1').count(), 1)
        self.assertTrue(compare_rows(before['credit_cases'], after['credit_cases'], before['credit_cases'].columns)['success'])
        self.assertEqual(result['metrics']['credit_cases']['updates'], 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IncrementalIntegrationTests))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
