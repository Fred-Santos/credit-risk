import os
from pathlib import Path
import subprocess
import sys
import unittest


class ExpansionIsolatedDeltaTests(unittest.TestCase):
    def test_revisions_and_abts_real_delta(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run([sys.executable,str(root/'tests/expansion_revision_integration.py')],
                              cwd=root,capture_output=True,text=True,timeout=300)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-14000:])
