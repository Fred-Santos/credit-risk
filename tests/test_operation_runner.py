from pathlib import Path
import subprocess
import unittest


class SupervisorProcessTests(unittest.TestCase):
    def test_supervisor_error_and_retry_contracts(self):
        result=subprocess.run(['bash','scripts/objects.sh','tests/operation_runner_checks.py'],
            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Ran 8 tests',result.stderr)
