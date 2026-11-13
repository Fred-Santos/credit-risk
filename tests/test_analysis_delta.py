from pathlib import Path
import subprocess
import unittest


class IsolatedAnalysisTests(unittest.TestCase):
    def test_analysis_in_clean_process(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['bash','scripts/analysis.sh','tests/analysis_integration.py'],cwd=root,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        self.assertEqual(result.returncode,0,result.stdout[-20000:])
        self.assertIn('Ran 6 tests',result.stdout)
        self.assertNotIn('skipped=',result.stdout)
        print('F07 Spark isolado: seis cenários analíticos aprovados, sem ignorados.')
