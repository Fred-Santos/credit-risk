import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from src.pipelines.build_sample import load_policy, select_cases, verify_committed
from src.quality.contracts import check_schema, load_contract, validate_snapshot, source_fingerprints

ROOT = Path(__file__).resolve().parents[1]


def fixture_policy():
    return {'version': 1, 'algorithm': 'sha256_seed_colon_case_id_v1', 'seed': 'test-seed',
            'max_cases': 4, 'week_min': 0, 'week_max': 2,
            'batches': [{'id': f'b{i}', 'min_week': i, 'max_week': i} for i in range(3)]}


class ContractConfigurationTests(unittest.TestCase):
    def test_every_input_file_must_have_a_fingerprint(self):
        contract = load_contract(ROOT / 'configs/contracts/home_credit_v1.yaml')
        filename = contract['tables']['train_base']['files'][0]
        del contract['sources'][filename]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'contract.yaml'
            path.write_text(yaml.safe_dump(contract))
            with self.assertRaisesRegex(ValueError, 'sem fingerprint'):
                load_contract(path)

    def test_source_edition_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'source.parquet'
            path.write_bytes(b'synthetic-fixture')
            expected = {'sha256': hashlib.sha256(b'synthetic-fixture').hexdigest(), 'bytes': len(b'synthetic-fixture')}
            contract = {'sources': {'source.parquet': expected}}
            self.assertEqual(source_fingerprints(root, contract)['source.parquet'], expected)
            path.write_bytes(b'different-fixture')
            with self.assertRaisesRegex(ValueError, 'Snapshot de origem'):
                source_fingerprints(root, contract)

    def test_invalid_policy_ranges_and_limit_fail(self):
        changes = [lambda p: p.update(max_cases=50001),
                   lambda p: p['batches'][1].update(min_week=0),
                   lambda p: p['batches'][1].update(min_week=2),
                   lambda p: p['batches'][1].update(id='b0')]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'policy.yaml'
            for change in changes:
                policy = fixture_policy()
                change(policy)
                path.write_text(yaml.safe_dump(policy))
                with self.subTest(policy=policy), self.assertRaises(ValueError):
                    load_policy(path)

    def test_reuse_rejects_changed_or_unregistered_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / 'sample.parquet'
            payload.write_bytes(b'synthetic-fixture')
            identity = {'fixture': True}
            (root / '_selection.json').write_text(json.dumps({
                'identity': identity,
                'output_checksums': {'sample.parquet': hashlib.sha256(b'synthetic-fixture').hexdigest()}}))
            verify_committed(root, identity)
            payload.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                verify_committed(root, identity)
            payload.write_bytes(b'synthetic-fixture')
            (root / 'extra.parquet').write_bytes(b'extra')
            with self.assertRaises(RuntimeError):
                verify_committed(root, identity)

    def test_key_must_be_required_non_null(self):
        contract = load_contract(ROOT / 'configs/contracts/home_credit_v1.yaml')
        contract['tables']['train_applprev_1']['required_non_null'] = ['case_id']
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'contract.yaml'
            path.write_text(yaml.safe_dump(contract))
            with self.assertRaisesRegex(ValueError, 'nulabilidade'):
                load_contract(path)


@unittest.skipUnless(importlib.util.find_spec('pyspark'), 'PySpark não instalado')
class SampleAndContractSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='sample-contract-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def frames_and_contract(self):
        frames = {
            'train_base': self.spark.createDataFrame(
                [(101, '2020-01-01', 202001, 0, 0), (102, '2020-01-02', 202001, 1, 1)],
                'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long'),
            'static': self.spark.createDataFrame([(101, None), (102, 2.0)], 'case_id long, amount double'),
            'history': self.spark.createDataFrame([], 'case_id long, num_group1 long, amount double'),
        }
        tables = {}
        for name, frame in frames.items():
            key = ['case_id', 'num_group1'] if name == 'history' else ['case_id']
            tables[name] = {'schema': dict(frame.dtypes), 'key': key,
                            'required_non_null': list(frame.columns) if name == 'train_base' else key,
                            'minimum_rows': 0 if name == 'history' else 1}
            if name != 'train_base':
                tables[name]['reference'] = {'table': 'train_base', 'columns': ['case_id'],
                                              'full_coverage': name == 'static'}
        return frames, {'tables': tables}

    def test_selection_matches_python_reference_independent_of_order_and_target(self):
        from pyspark.sql import functions as F
        frame = self.spark.createDataFrame([(i, i % 3, i % 2) for i in range(10)],
                                           'case_id long, WEEK_NUM long, target long')
        policy = fixture_policy()
        expected = sorted(sorted(range(10), key=lambda i: (hashlib.sha256(f'test-seed:{i}'.encode()).hexdigest(), i))[:4])
        actual = select_cases(frame, policy).collect()
        self.assertEqual(sorted(r.case_id for r in actual), expected)
        self.assertTrue(all(r._batch_id == f'b{r.WEEK_NUM}' for r in actual))
        changed = frame.withColumn('target', 1 - F.col('target')).orderBy(F.desc('case_id')).repartition(3)
        self.assertEqual(sorted(r.case_id for r in select_cases(changed, policy).collect()), expected)

    def test_optional_null_and_absent_history_are_accepted(self):
        frames, contract = self.frames_and_contract()
        result = validate_snapshot(frames, contract)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['tables']['history']['parent_keys_without_match'], 2)
        amount = next(c for c in result['tables']['static']['schema'] if c['column'] == 'amount')
        self.assertEqual(amount['null_count'], 1)

    def test_orphan_and_required_null_block_snapshot(self):
        from pyspark.sql import functions as F
        frames, contract = self.frames_and_contract()
        frames['train_base'] = frames['train_base'].withColumn('target', F.lit(None).cast('long'))
        frames['history'] = self.spark.createDataFrame([(999, 0, 1.0)], 'case_id long, num_group1 long, amount double')
        result = validate_snapshot(frames, contract)
        self.assertEqual(result['status'], 'failed')
        failed = {(r['table'], r['check']) for r in result['checks'] if not r['success']}
        self.assertIn(('train_base', 'required_non_null'), failed)
        self.assertIn(('history', 'foreign_key'), failed)

    def test_extra_column_cannot_be_ignored(self):
        from pyspark.sql import functions as F
        frames, contract = self.frames_and_contract()
        with self.assertRaisesRegex(ValueError, 'extra='):
            check_schema(frames['train_base'].withColumn('unexpected', F.lit(1)), contract['tables']['train_base'])
