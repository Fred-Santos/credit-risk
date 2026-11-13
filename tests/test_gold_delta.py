from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedGoldTests(unittest.TestCase):
    def test_gold_delta_in_clean_jvm(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'tests/gold_integration.py')], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1200)
        self.assertEqual(result.returncode, 0, result.stdout[-24000:])
        self.assertIn('Ran 8 tests', result.stdout)
        self.assertNotIn('skipped=', result.stdout)
        print('F06 Delta isolado: oito cenários aprovados, sem ignorados.')
