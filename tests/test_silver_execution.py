"""Diagnóstico operacional sem iniciar JVM ou acessar a fonte externa."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.pipelines.run_silver_initial import main, run_silver_initial
from src.utils.run_context import RunContext

ROOT = Path(__file__).resolve().parents[1]


class SilverExecutionDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = RunContext.create(Path(self.temp.name))
        self.report = self.ctx.repo_root / 'artifacts/silver_runs' / f'{self.ctx.run_id}.json'

    def test_invalid_selection_is_reported_before_io_or_spark(self):
        with self.assertRaisesRegex(ValueError, 'selection_id'):
            run_silver_initial(self.ctx, None, '../escape')
        report = json.loads(self.report.read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['error_type'], 'ValueError')
        self.assertFalse(list(self.ctx.silver_dir.rglob('acceptances/*.json')))

    def test_run_id_cannot_replace_prior_report(self):
        self.report.parent.mkdir(parents=True)
        self.report.write_text('preserve previous execution')
        with self.assertRaisesRegex(FileExistsError, 'run_id'):
            run_silver_initial(self.ctx, None, 'f' * 24)
        self.assertEqual(self.report.read_text(), 'preserve previous execution')

    def test_spark_start_failure_is_reported(self):
        with patch('sys.argv', ['run_silver_initial', '--sample', 'a' * 24]), \
             patch('src.pipelines.run_silver_initial.RunContext.create', return_value=self.ctx), \
             patch('src.pipelines.run_silver_initial.create_spark_session', side_effect=RuntimeError('JVM unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'JVM unavailable'):
                main()
        report = json.loads(self.report.read_text())
        self.assertEqual((report['status'], report['stage']), ('failed', 'spark_start'))

    def test_cli_failure_returns_nonzero_without_jvm(self):
        result = subprocess.run([sys.executable, '-m', 'src.pipelines.run_silver_initial', '--sample', '../invalid'],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('selection_id', result.stderr)


if __name__ == '__main__':
    unittest.main()
