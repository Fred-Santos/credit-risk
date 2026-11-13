from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import yaml

from src.gold.model import load_gold_contract

ROOT = Path(__file__).resolve().parents[1]


class GoldPolicyTests(unittest.TestCase):
    def test_gold_contract_rejects_changed_grain_schema_and_temporal_claim(self):
        original = yaml.safe_load((ROOT / 'configs/contracts/gold_v1.yaml').read_text())
        changes = [{'abt_grain': 'observation'}, {'silver_contract_sha256': 'bad'},
                   {'temporal_availability': 'point_in_time'}, {'zero_denominator': 'zero_rate'}, {'version': True}]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'gold.yaml'
            for change in changes:
                path.write_text(yaml.safe_dump({**original, **change}))
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_gold_contract(path, ROOT / 'configs/contracts/silver_managed_v2.yaml')
            modified = deepcopy(original)
            modified['schemas']['abt']['case_id'] = 'string'
            path.write_text(yaml.safe_dump(modified))
            with self.assertRaises(ValueError):
                load_gold_contract(path, ROOT / 'configs/contracts/silver_managed_v2.yaml')

    def test_gold_contract_exposes_null_and_numeric_rules(self):
        spec = load_gold_contract(ROOT / 'configs/contracts/gold_v1.yaml',
                                  ROOT / 'configs/contracts/silver_managed_v2.yaml')
        self.assertEqual(spec['all_null_amounts'], 'zero_non_null_count_null_sum_mean_min_max')
        self.assertEqual(spec['missing_history'], 'zero_counts_false_flag_null_amounts_and_revision')
        self.assertEqual(len(spec['schemas']['abt']), 19)
        self.assertEqual(len(spec['schemas']['monthly_metrics']), 11)
