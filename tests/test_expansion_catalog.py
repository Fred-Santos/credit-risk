"""Fronteiras do catálogo: treino, identidade, shards e duplicação."""
import tempfile
import unittest
from pathlib import Path
import yaml
from scripts.acquire_expansion import load_files


class ExpansionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'configs').mkdir()
        self.catalog = {'version': 1, 'competition': 'home-credit-credit-risk-model-stability',
                        'scope': 'all_train_parquet', 'dictionary': 'feature_definitions.csv',
                        'tables': {'train_static_0': [
                            {'name': 'parquet_files/train/train_static_0_0.parquet', 'bytes': 12}]}}

    def load(self):
        (self.root / 'configs/home_credit_expansion_catalog.yaml').write_text(yaml.safe_dump(self.catalog))
        return load_files(self.root)

    def test_dictionary_and_shards_selected_once(self):
        self.assertEqual(self.load()[1], ['feature_definitions.csv',
                                         'parquet_files/train/train_static_0_0.parquet'])

    def test_test_files_traversal_wrong_table_and_duplicate_rejected(self):
        original = self.catalog['tables']['train_static_0'][0]
        for path in ('parquet_files/test/test_static_0_0.parquet',
                     'parquet_files/train/../test/train_static_0_0.parquet',
                     'parquet_files/train/train_person_1.parquet'):
            with self.subTest(path=path):
                self.catalog['tables']['train_static_0'] = [{'name': path, 'bytes': 12}]
                with self.assertRaises(ValueError): self.load()
        self.catalog['tables']['train_static_0'] = [original, original]
        with self.assertRaises(ValueError): self.load()

    def test_invalid_size_and_identity_rejected(self):
        self.catalog['tables']['train_static_0'][0]['bytes'] = -1
        with self.assertRaises(ValueError): self.load()
        self.catalog['competition'] = 'other'
        with self.assertRaises(ValueError): self.load()
