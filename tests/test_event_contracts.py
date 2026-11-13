from itertools import permutations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.bronze.event_batches import publish_batch
from src.quality.event_contracts import (EventConflictError, check_revision_history,
    load_event_contract, make_event, revision_action, validate_event)


class EventContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.contract, cls.snapshot = load_event_contract(
            root / 'configs/contracts/home_credit_events_v1.yaml',
            root / 'configs/contracts/home_credit_v1.yaml')

    def setUp(self):
        self.payload = {'case_id': 1, 'date_decision': '2019-01-01',
                        'MONTH': 201901, 'WEEK_NUM': 0, 'target': 0}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.selection = 'a' * 24
        self.root = Path(self.temp.name) / self.selection / 'test_stream'
        self.binding = {'selection_id': self.selection, 'snapshot_contract_sha256': 'fixture'}

    def event(self, **changes):
        args = dict(selection_id=self.selection, stream_id='test_stream', batch_id='batch_a',
                    table='train_base', ordinal=0, source_revision=1,
                    payload=self.payload, scenario='baseline_replay', payload_origin='synthetic_fixture')
        args.update(changes)
        return make_event(self.contract, self.snapshot, **args)

    def publish(self, events, batch='batch_a', run='run_a'):
        return publish_batch(self.root, binding=self.binding, stream_id='test_stream',
                             batch_id=batch, events=events, contract=self.contract,
                             snapshot=self.snapshot, run_id=run, started_at_utc='fixture_time')

    def revised(self, revision=2, batch='batch_b', target=1):
        return self.event(source_revision=revision, batch_id=batch,
                          payload={**self.payload, 'target': target}, scenario='late_arrival')

    def test_identity_stable_across_deliveries_and_payload_order(self):
        a = self.event()
        b = self.event(batch_id='batch_b', ordinal=4,
                       payload=dict(reversed(list(self.payload.items()))), scenario='duplicate_delivery')
        self.assertEqual(a['_event_id'], b['_event_id'])
        self.assertEqual(a['_payload_sha256'], b['_payload_sha256'])
        self.assertNotEqual(a['_delivery_id'], b['_delivery_id'])
        self.assertNotEqual(a['_event_id'], self.revised()['_event_id'])

    def test_business_key_composite_and_context_separate_identity(self):
        payload = {name: None for name in self.snapshot['tables']['train_applprev_1']['schema']}
        payload.update(case_id=1, num_group1=0)
        a = self.event(table='train_applprev_1', payload=payload)
        b = self.event(table='train_applprev_1', payload={**payload, 'num_group1': 1})
        self.assertNotEqual(a['_event_id'], b['_event_id'])
        self.assertNotEqual(a['_event_id'], self.event(table='train_applprev_1', payload=payload,
                                                      stream_id='other_stream')['_event_id'])

    def test_payload_requires_full_typed_row_and_valid_base_domains(self):
        invalid = [{**self.payload, 'case_id': True}, {**self.payload, 'case_id': 2**63},
                   {**self.payload, 'target': None}, {**self.payload, 'target': 2},
                   {**self.payload, 'MONTH': 202001}, {**self.payload, 'date_decision': '2019-02-30'},
                   {**self.payload, 'WEEK_NUM': -1}, {**self.payload, 'extra': 0},
                   {k: v for k, v in self.payload.items() if k != 'MONTH'}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.event(payload=payload)

    def test_optional_nulls_preserved_and_double_encoding_normalized(self):
        payload = {name: None for name in self.snapshot['tables']['train_static_0']['schema']}
        payload.update(case_id=1, annuity_780A=0)
        a = self.event(table='train_static_0', payload=payload)
        b = self.event(table='train_static_0', payload={**payload, 'annuity_780A': -0.0})
        self.assertEqual(a['_payload_sha256'], b['_payload_sha256'])
        self.assertIsNone(a['_payload']['credamount_770A'])
        for value in (float('nan'), float('inf'), True, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.event(table='train_static_0', payload={**payload, 'annuity_780A': value})

    def test_envelope_tampering_and_unmarked_simulation_rejected(self):
        for field, value in [('_is_simulated', False), ('_payload_sha256', 'bad'),
                             ('_event_id', 'bad'), ('_delivery_id', 'bad'),
                             ('_event_contract_version', True), ('_operation', 'delete')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_event({**self.event(), field: value}, self.contract, self.snapshot)
        for changes in ({'source_revision': True}, {'ordinal': -1}, {'stream_id': '../escape'},
                        {'source_revision': 0}, {'scenario': 'correction_simulation'},
                        {'source_revision': 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.event(**changes)

    def test_conflict_detected_even_for_old_revision_after_newer_version(self):
        history = [self.event(), self.revised()]
        old_conflict = self.event(payload={**self.payload, 'target': 1}, batch_id='batch_c')
        with self.assertRaises(EventConflictError):
            check_revision_history(history + [old_conflict])

    def test_reference_state_independent_of_arrival_order(self):
        versions = [self.event(), self.revised(2), self.revised(3, batch='batch_c', target=0)]
        for order in permutations(versions):
            check_revision_history(list(order))
            current = None
            for event in order:
                if revision_action(current, event, self.snapshot) in ('insert', 'update'):
                    current = event
            self.assertEqual(current['_source_revision'], 3)
        self.assertEqual(revision_action(versions[2], versions[0], self.snapshot), 'ignore_older_revision')
        self.assertEqual(revision_action(versions[0], versions[0], self.snapshot), 'ignore_same_revision')

    def test_different_keys_cannot_be_compared_as_same_state(self):
        other = self.event(payload={**self.payload, 'case_id': 2})
        with self.assertRaises(ValueError):
            revision_action(self.event(), other, self.snapshot)

    def test_retry_preserves_first_receipt_and_input_order_not_significant(self):
        events = [self.event(), self.event(ordinal=1, scenario='duplicate_delivery')]
        first = self.publish(events)
        again = self.publish(list(reversed(events)), run='new_run')
        self.assertFalse(first['reused'])
        self.assertTrue(again['reused'])
        self.assertEqual(first['first_run_id'], again['first_run_id'])
        self.assertEqual(again['event_count'], 2)
        self.assertEqual(again['receipt_index'], 1)

    def test_duplicate_position_and_changed_batch_content_rejected(self):
        with self.assertRaises(ValueError):
            self.publish([self.event(), self.event()])
        self.publish([self.event()])
        with self.assertRaises(ValueError):
            self.publish([self.event(), self.event(ordinal=1)])

    def test_entire_conflicting_batch_rejected_without_partial_delivery(self):
        self.publish([self.event()])
        conflict = self.event(batch_id='batch_b', payload={**self.payload, 'target': 1})
        valid = self.event(batch_id='batch_b', ordinal=1, source_revision=2,
                           scenario='late_arrival', payload={**self.payload, 'target': 1})
        with self.assertRaises(EventConflictError):
            self.publish([valid, conflict], batch='batch_b')
        self.assertFalse((self.root / 'batch_b').exists())

    def test_late_events_and_duplicates_preserved_in_immutable_history(self):
        self.publish([self.event()])
        self.publish([self.revised()], batch='batch_b')
        result = self.publish([self.event(batch_id='batch_c', scenario='late_arrival')], batch='batch_c')
        self.assertEqual(result['receipt_index'], 3)
        old_conflict = self.event(batch_id='batch_d', payload={**self.payload, 'target': 1})
        with self.assertRaises(EventConflictError):
            self.publish([old_conflict], batch='batch_d')
        self.assertFalse((self.root / 'batch_d').exists())

    def test_failure_before_commit_can_be_retried(self):
        with patch('pathlib.Path.rename', side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):
                self.publish([self.event()])
        self.assertFalse((self.root / 'batch_a').exists())
        self.assertFalse(list(self.root.glob('.stage_*')))
        self.assertFalse(self.publish([self.event()])['reused'])

    def test_corrupt_published_packet_blocks_retry_and_new_batches(self):
        self.publish([self.event()])
        (self.root / 'batch_a/events.jsonl').write_text('{}\n')
        for batch, event in [('batch_a', self.event()), ('batch_b', self.revised())]:
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                self.publish([event], batch=batch)

    def test_context_binding_cannot_change_and_event_context_checked(self):
        self.publish([self.event()])
        self.binding = {**self.binding, 'snapshot_contract_sha256': 'changed'}
        with self.assertRaises(ValueError):
            self.publish([self.revised()], batch='batch_b')
        with self.assertRaises(ValueError):
            self.publish([self.event(batch_id='other_batch')])


if __name__ == '__main__':
    unittest.main()
