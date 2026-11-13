from pathlib import Path
import tempfile
import unittest

from src.utils.paths import load_paths
from src.utils.run_context import RunContext


class PathConfigurationTests(unittest.TestCase):
    def test_custom_paths_reach_execution_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'configs').mkdir()
            (root / 'configs/paths.yaml').write_text(
                'data: {raw: inputs, bronze: outputs/bronze}\n'
                'docs: {root: reports, data_quality: reports/checks}\n')
            ctx = RunContext.create(root)
            self.assertEqual(ctx.raw_dir, root / 'inputs')
            self.assertEqual(ctx.bronze_dir, root / 'outputs/bronze')
            self.assertEqual(ctx.data_quality_dir, root / 'reports/checks')
            self.assertEqual(ctx.lineage_dir, root / 'reports/lineage')

    def test_invalid_and_overlapping_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'configs').mkdir()
            config = root / 'configs/paths.yaml'
            for content in ['data: {raw: ../outside}', 'data: {raw: /tmp}',
                            'data: {raw: data, bronze: data/bronze}',
                            'docs: {root: null}', 'data: {typo: inputs}']:
                config.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_paths(root)
