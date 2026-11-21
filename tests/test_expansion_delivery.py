from pathlib import Path
import subprocess
import sys
import unittest


class ExpansionDeliveryDeltaTests(unittest.TestCase):
    def test_public_analysis_delta_fixture(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run([sys.executable,str(root/'tests/expansion_delivery_integration.py')],cwd=root,capture_output=True,text=True,timeout=300)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-12000:])


class ExpansionDeliveryObjectTests(unittest.TestCase):
    def test_publication_failure_recovery_and_historical_integrity(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['bash','scripts/objects.sh','tests/expansion_object_delivery_integration.py'],cwd=root,capture_output=True,text=True,timeout=600)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-14000:])


class ExpansionPublicationPolicyTests(unittest.TestCase):
    def test_stream_upload_never_overwrites_divergent_existing_object(self):
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import Mock
        from src.expansion.publication import put_file_once
        from src.pipelines.download_home_credit import sha256
        with TemporaryDirectory() as folder:
            path=Path(folder)/'payload';path.write_bytes(b'approved')
            client=SimpleNamespace(exists=lambda key:True,checksum=lambda key:'different',s3=Mock(),bucket='fixture')
            with self.assertRaises(ValueError):put_file_once(client,'fixture/key',path,sha256(path))
            client.s3.put_object.assert_not_called()

    def test_delta_logs_cannot_escape_the_mirrored_snapshot(self):
        from tempfile import TemporaryDirectory
        import json
        from src.expansion.publication import relative_delta_actions
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'_delta_log').mkdir()
            log=root/'_delta_log/00000000000000000000.json'
            for value in ('../outside.parquet','/absolute.parquet','s3a://other/table/part.parquet'):
                log.write_text(json.dumps({'add':{'path':value}})+'\n')
                with self.subTest(path=value),self.assertRaises(ValueError):relative_delta_actions(root,{str(log.relative_to(root)):'fixture'})
