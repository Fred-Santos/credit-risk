from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from src.pipelines.run_incremental_demo import load_incremental_policy, run_incremental_demo
from src.utils.run_context import RunContext

ROOT = Path(__file__).resolve().parents[1]


class IncrementalPolicyTests(unittest.TestCase):
    def test_unsupported_precedence_deletes_and_untyped_changes_are_blocked(self):
        original = load_incremental_policy(ROOT / 'configs/incremental_policy_v1.yaml')
        changes = [lambda p: p.update(precedence='arrival_time'),
                   lambda p: p.update(absence='delete_missing'),
                   lambda p: p.update(version=True),
                   lambda p: p['corrections']['train_static_0'].update(add=True)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'policy.yaml'
            for change in changes:
                value = deepcopy(original)
                change(value)
                path.write_text(yaml.safe_dump(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    load_incremental_policy(path)

    def test_missing_configuration_leaves_failed_run_report(self):
        with tempfile.TemporaryDirectory() as temp:
            ctx = RunContext.create(Path(temp))
            with self.assertRaises(FileNotFoundError):
                run_incremental_demo(ctx, None, 'a' * 24)
            report = json.loads((ctx.repo_root / 'artifacts/f04/runs' / f'{ctx.run_id}.json').read_text())
            self.assertEqual((report['status'], report['stage']), ('failed', 'configuration'))
