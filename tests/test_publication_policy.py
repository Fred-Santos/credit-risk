from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import yaml

from src.publication.evolution import load_managed_contract
from src.publication.protocol import load_publication_policy

ROOT = Path(__file__).resolve().parents[1]


class PublicationPolicyTests(unittest.TestCase):
    def test_retention_and_commit_policy_cannot_be_relaxed_silently(self):
        original = load_publication_policy(ROOT / 'configs/publication_policy_v1.yaml')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'policy.yaml'
            for change in ({'retention_days': 0}, {'retention_days': 30.0}, {'version': True},
                           {'real_vacuum': 'allowed'}, {'visibility': 'read_latest_table_version'}):
                path.write_text(yaml.safe_dump({**original, **change}))
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_publication_policy(path)

    def test_only_authorized_column_and_parent_contract_are_accepted(self):
        path = ROOT / 'configs/contracts/silver_managed_v2.yaml'
        parent = ROOT / 'configs/contracts/silver_initial_v1.yaml'
        original = load_managed_contract(path, parent)
        changes = [lambda c: c.update(parent_contract_sha256='invalid'),
                   lambda c: c['added_columns'].update(_silver_contract_version='string'),
                   lambda c: c['added_columns'].update(unexpected='double'),
                   lambda c: c.update(version=2.0)]
        with tempfile.TemporaryDirectory() as temp:
            for change in changes:
                value = deepcopy(original)
                change(value)
                modified = Path(temp) / 'contract.yaml'
                modified.write_text(yaml.safe_dump(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    load_managed_contract(modified, parent)
