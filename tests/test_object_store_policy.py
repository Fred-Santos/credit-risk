from pathlib import Path
import tempfile
import unittest

import yaml

from src.object_store.config import load_config,s3_key

ROOT=Path(__file__).resolve().parents[1]


class ObjectStorePolicyTests(unittest.TestCase):
    def test_external_endpoints_path_overlap_and_policy_drift_block(self):
        original=load_config(ROOT)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'configs').mkdir()
            for change in ({'endpoint':'http://0.0.0.0:18333'},{'data_directory':'data/raw'},
                {'hadoop_aws':'3.4.3'},{'real_vacuum':'allowed'},{'retention_days':30.0},
                {'master_port':18333},{'version':True}):
                (root/'configs/object_store_v1.yaml').write_text(yaml.safe_dump({**original,**change}))
                with self.subTest(change=change),self.assertRaises(ValueError):load_config(root)

    def test_object_keys_are_not_filesystem_paths(self):
        for value in ('/absolute','../outside','a/../b','a//b','a\\b',''):
            with self.subTest(value=value),self.assertRaises(ValueError):s3_key(value)
        self.assertEqual(s3_key('lakehouse-v1/a/'),'lakehouse-v1/a/')
