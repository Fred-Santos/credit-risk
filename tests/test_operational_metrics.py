import unittest
from src.operation.metrics import StageClock, batch_counters, publication_inventory


class OperationalMetricsTests(unittest.TestCase):
    def test_stage_clock_is_exclusive_and_accumulates_repeated_stage(self):
        values=iter([0,1,4,6,10,12])
        timer=StageClock(lambda:next(values))
        timer.enter('inputs');timer.enter('merge');timer.enter('inputs');timer.enter('metrics')
        result=timer.snapshot()
        self.assertEqual(result['total_seconds'],12)
        self.assertEqual(result['stage_seconds'],{'unattributed':1,'inputs':7,'merge':2,'metrics':2})
        self.assertEqual(sum(result['stage_seconds'].values()),12)

    def test_deliveries_balance_and_replay_does_not_invent_inserts(self):
        first={'input_deliveries':8,'duplicate_deliveries':2,'superseded_revisions':1,
               'inserts':3,'updates':1,'ignored_same_revision':0,'ignored_older_revision':1}
        replay={**first,'inserts':0,'updates':0,'ignored_same_revision':4}
        result=batch_counters([{'metrics':{'cases':first}},{'metrics':{'cases':replay}}])
        actual=result['tables']['cases']
        self.assertEqual(actual['input_deliveries'],16)
        self.assertEqual(actual['inserts'],3);self.assertEqual(actual['updates'],1)
        self.assertEqual(sum(v for k,v in actual.items() if k!='input_deliveries'),16)
        self.assertEqual(batch_counters([])['tables'],{})

    def test_inventory_counts_retained_objects_without_spark_actions(self):
        class Client:
            def list(self,prefix):
                self.prefix=prefix
                return {'p/old.parquet':100,'p/new.parquet':120,'p/_delta_log/0.json':30,'p/_delta_log/_commits/':0}
        client=Client()
        result=publication_inventory(client,{'tables':{'gold.abt':{'key':'p','rows':3}}})
        self.assertEqual(client.prefix,'p/')
        self.assertEqual(result['total_logical_bytes'],250)
        self.assertEqual(result['tables']['gold.abt']['parquet_files'],2)
        self.assertEqual(result['total_files'],3)
        self.assertEqual(result['total_objects'],4)
        self.assertEqual(result['tables']['gold.abt']['directory_markers'],1)
        self.assertEqual(result['tables']['gold.abt']['delta_log_files'],1)
