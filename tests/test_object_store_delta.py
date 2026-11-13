from pathlib import Path
import subprocess
import unittest


class IsolatedObjectStorageTests(unittest.TestCase):
    def test_s3a_delta_in_clean_process(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['bash','scripts/objects.sh','tests/object_store_integration.py'],cwd=root,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1800)
        self.assertEqual(result.returncode,0,result.stdout[-30000:])
        self.assertIn('Ran 10 tests',result.stdout)
        self.assertNotIn('skipped=',result.stdout)
        print('F08 SeaweedFS/S3A/Delta: dez cenários aprovados, sem ignorados.')
