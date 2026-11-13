"""Integração F04 obrigatória, isolada em JVM com Delta desde o início."""
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedIncrementalTests(unittest.TestCase):
    def test_incremental_delta_in_clean_jvm(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'tests/incremental_integration.py')],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=1200)
        self.assertEqual(result.returncode, 0, result.stdout[-24000:])
        self.assertIn('Ran 9 tests', result.stdout)
        self.assertNotIn('skipped=', result.stdout)
        print('F04 Delta isolado: 9 cenários aprovados, sem testes ignorados.')
