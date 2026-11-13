"""Delta precisa de uma JVM iniciada com seus JARs, isolada dos testes Spark SQL."""
from pathlib import Path
import subprocess
import sys
import unittest


class IsolatedDeltaTests(unittest.TestCase):
    def test_initial_delta_in_clean_jvm(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'tests/delta_initial_integration.py')],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-18000:])
        self.assertIn('Ran 15 tests', result.stdout)
        self.assertNotIn('skipped=', result.stdout)
        print('Delta isolado: 15 cenários aprovados em JVM própria, sem testes ignorados.')
