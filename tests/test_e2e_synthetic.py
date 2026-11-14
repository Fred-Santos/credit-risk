from pathlib import Path
import subprocess
import unittest


class SyntheticEndToEndTests(unittest.TestCase):
    def test_raw_to_published_s3_with_invented_data(self):
        result=subprocess.run(['bash','scripts/objects.sh','tests/e2e_synthetic.py'],cwd=Path(__file__).resolve().parents[1],
            capture_output=True,text=True,timeout=2400)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-25000:])
        self.assertIn('synthetic_e2e_passed',result.stdout)
