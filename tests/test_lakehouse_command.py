import unittest
from src.pipelines.run_lakehouse import select_packets


class OperationalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.packets = [({'batch_id': n}, {}) for n in ('initial', 'correction', 'late')]

    def test_update_includes_dependencies_in_order(self):
        self.assertEqual([m['batch_id'] for m,_ in select_packets(self.packets,'update','correction')], ['initial','correction'])

    def test_replay_and_rebuild_use_complete_input_unless_bounded(self):
        for mode in ('replay','rebuild'):
            self.assertEqual(select_packets(self.packets,mode,None),self.packets)
            self.assertEqual(len(select_packets(self.packets,mode,'initial')),1)

    def test_missing_or_unknown_batch_and_mode_fail(self):
        for mode,batch in [('update',None),('update','missing'),('erase',None)]:
            with self.assertRaises(ValueError): select_packets(self.packets,mode,batch)
