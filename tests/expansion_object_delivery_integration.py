from pathlib import Path
import sys,tempfile,unittest,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from expansion_delivery_fixture import fixture
from src.expansion.analysis import build_analysis
from src.expansion.delivery import exercise
from src.expansion.publication import consume,registry
from src.object_store.client import ObjectClient
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.object_store.publication import current


class ObjectDeliveryTest(unittest.TestCase):
    def test_fault_recovery_source_closure_immutable_history_and_label_guard(self):
        service=ObjectService(ROOT);preexisting=service.status()['status']=='running';service.start()
        spark=create_object_spark(ROOT,app_name='expansion-object-fixture')
        client=ObjectClient(ROOT);client.config={**client.config,'prefix':'fixtures/expansion-delivery/'+uuid.uuid4().hex}
        prefix=client.config['prefix']
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);bundles=[]
                for variant in (0,1):
                    repo=root/str(variant);repo.mkdir();silver,gold,policy=fixture(repo,spark,variant)
                    a,_=build_analysis(repo,spark,silver,gold,policy,render=False)
                    bundles.append((repo,(silver,gold,repo/'data/gold/expansion-analysis'/a['id'])))
                # Um repo pode conter os dois snapshots; mover o segundo preserva paths relativos dos pins.
                import shutil
                repo,base=bundles[0];second_repo,second=bundles[1]
                for p in (second_repo/'data/silver/expansion').iterdir():
                    if not p.name.startswith('.'):shutil.copytree(p,repo/'data/silver/expansion'/p.name)
                for folder in ('expansion','expansion-analysis'):
                    for p in (second_repo/'data/gold'/folder).iterdir():
                        if not p.name.startswith('.'):shutil.copytree(p,repo/'data/gold'/folder/p.name)
                changed=tuple(repo/p.relative_to(second_repo) for p in second)
                result=exercise(repo,client,spark,base,changed,repo/'result.json')
                self.assertEqual(result['status'],'passed');self.assertTrue(result['current_restored_to_real_baseline'])
                self.assertEqual(current(client,registry(client,'a'*24))[0]['publication_id'],result['baseline_id'])
                manifest,frames=consume(client,spark,'a'*24)
                self.assertEqual(len(manifest['tables']),12);self.assertNotIn('gold.evaluation_labels',frames);self.assertNotIn('target',frames['silver.train_base'].columns)
                # Corrupção fica restrita ao histórico inventado, nunca ao CURRENT real do projeto.
                old,_=consume(client,spark,'a'*24,result['corrected_id'])
                entry=next(iter(old['tables'].values()));key=entry['key']+'/'+next(iter(entry['files']))
                client.s3.put_object(Bucket=client.bucket,Key=key,Body=b'corrupt')
                with self.assertRaises(ValueError):consume(client,spark,'a'*24,result['corrected_id'])
        finally:
            spark.stop()
            for key in client.list(prefix+'/'):client.s3.delete_object(Bucket=client.bucket,Key=key)
            if not preexisting:service.stop()


if __name__=='__main__':unittest.main(verbosity=2)
