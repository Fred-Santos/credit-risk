"""Suíte Delta executada em JVM própria; não depende do Kaggle."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import yaml
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.silver.initial_delta import TABLES, identity_digest, materialize_initial, open_initial_tables
from src.pipelines.download_home_credit import sha256


class InitialDeltaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        from pyspark.sql import functions as F
        cls.spark = create_spark_session(ROOT, app_name='initial-delta-tests', delta=True)
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions', '2')
        cls.temp = tempfile.TemporaryDirectory()
        cls.identity = {'fixture': 'initial_delta_v1'}
        cls.frames = {
            'train_base': cls.spark.createDataFrame([(1, '2020-01-01', 0), (2, '2020-02-29', 1)],
                'case_id long, date_decision string, target long').withColumn('date_decision', F.to_date('date_decision')),
            'train_static_0': cls.spark.createDataFrame([(1, 99.0), (2, None)], 'case_id long, amount double'),
            'train_applprev_1': cls.spark.createDataFrame([(1, 0), (1, 1), (2, 0)], 'case_id long, num_group1 long')}
        cls.frames['train_base'] = (cls.frames['train_base']
            .withColumn('MONTH', F.date_format('date_decision', 'yyyyMM').cast('long'))
            .withColumn('WEEK_NUM', F.lit(0).cast('long')))
        cls.frames = {name: (frame.withColumn('_run_id', F.lit('fixture_run'))
            .withColumn('_source_file', F.lit('file:///fixture.parquet'))
            .withColumn('_ingest_date', F.lit('2020-01-01').cast('date'))
            .withColumn('ingest_batch', F.lit('fixture_batch'))) for name, frame in cls.frames.items()}
        cls.keys = {name: ['case_id', 'num_group1'] if name == 'train_applprev_1' else ['case_id'] for name in TABLES}
        cls.seed = materialize_initial(Path(cls.temp.name) / 'template', cls.spark, identity=cls.identity,
            frames=cls.frames, keys=cls.keys, run_id='first_run')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        # Paths próprios evitam reutilizar caches Delta de uma tabela mutada por outro teste.
        self.parent = Path(self.temp.name) / self._testMethodName
        self.root = self.parent / identity_digest(self.identity)[:24]
        shutil.copytree(self.seed['root'], self.root)

    def materialize(self, frames=None):
        return materialize_initial(self.parent, self.spark, identity=self.identity,
            frames=frames or self.frames, keys=self.keys, run_id='retry_run')

    def test_delta_read_after_relocation_preserves_schema_and_values(self):
        with open_initial_tables(self.root, self.spark) as (frames, manifest):
            self.assertEqual({n: f.count() for n, f in frames.items()},
                             {'credit_cases': 2, 'credit_static': 2, 'previous_applications': 3})
            self.assertEqual(dict(frames['credit_cases'].dtypes)['date_decision'], 'date')
            self.assertEqual(sorted((r.case_id, r.amount) for r in frames['credit_static'].collect()), [(1, 99.0), (2, None)])
            self.assertEqual({t['version'] for t in manifest['tables'].values()}, {0})

    def test_retry_keeps_manifest_uuid_and_version_zero(self):
        before = sha256(self.root / '_materialization.json')
        result = self.materialize()
        self.assertTrue(result['reused'])
        self.assertEqual(before, sha256(self.root / '_materialization.json'))
        self.assertEqual(result['manifest']['created_by_run_id'], 'first_run')

    def test_same_identity_different_payload_cannot_overwrite(self):
        from pyspark.sql import functions as F
        frames = {**self.frames, 'train_static_0': self.frames['train_static_0'].withColumn('amount', F.lit(999.0))}
        before = sha256(self.root / '_materialization.json')
        with self.assertRaisesRegex(ValueError, 'conteúdo diferente'):
            self.materialize(frames)
        self.assertEqual(before, sha256(self.root / '_materialization.json'))

    def test_altered_or_missing_files_block_delta_reader(self):
        file = next((self.root / 'credit_static').glob('*.parquet'))
        file.unlink()
        with self.assertRaisesRegex(ValueError, 'ausentes, extras ou alterados'):
            with open_initial_tables(self.root, self.spark):
                pass

    def test_existing_unbound_directory_is_never_overwritten(self):
        shutil.rmtree(self.root)
        self.root.mkdir()
        marker = self.root / 'keep.txt'
        marker.write_text('preserve')
        with self.assertRaises((OSError, ValueError)):
            self.materialize()
        self.assertEqual(marker.read_text(), 'preserve')

    def test_failure_before_bundle_publication_leaves_no_partial_package(self):
        shutil.rmtree(self.root)
        with patch('pathlib.Path.rename', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                self.materialize()
        self.assertFalse(self.root.exists())
        self.assertFalse(list(self.parent.glob('.initial_stage_*')))
        self.assertFalse(self.materialize()['reused'])

    def test_external_commit_is_rejected_by_immutable_initial_reader(self):
        from delta.tables import DeltaTable
        DeltaTable.forPath(self.spark, str(self.root / 'credit_cases')).delete('case_id = 1')
        with self.assertRaises(ValueError):
            with open_initial_tables(self.root, self.spark):
                pass

    def test_plain_parquet_ignores_delta_removals(self):
        from delta.tables import DeltaTable
        path = self.parent / 'illustration'
        self.frames['train_base'].coalesce(1).write.format('delta').save(str(path))
        DeltaTable.forPath(self.spark, str(path)).delete('case_id = 1')
        logical = self.spark.read.format('delta').load(str(path)).count()
        physical = self.spark.read.parquet(str(path)).count()
        self.assertEqual(logical, 1)
        self.assertGreater(physical, logical)

    def test_silver_contracts_on_persisted_tables_match_hand_oracle(self):
        from src.quality.bronze_contract import METADATA
        from src.quality.silver_contracts import DOMAINS, RELATIONSHIPS, validate_silver_frames
        # Expectativas declaradas à parte dos schemas do writer/manifesto.
        schemas = {
            'credit_cases': {'case_id': 'bigint', 'date_decision': 'date', 'MONTH': 'bigint', 'WEEK_NUM': 'bigint', 'target': 'bigint'},
            'credit_static': {'case_id': 'bigint', 'amount': 'double'},
            'previous_applications': {'case_id': 'bigint', 'num_group1': 'bigint'}}
        plan = {'domains': DOMAINS, 'tables': {}}
        for name, schema in schemas.items():
            key = ['case_id', 'num_group1'] if name == 'previous_applications' else ['case_id']
            plan['tables'][name] = {'schema': {**schema, **METADATA}, 'key': key,
                'grain': 'synthetic_fixture', 'required_non_null': (list(schema) if name == 'credit_cases' else key) + list(METADATA),
                'minimum_rows': 0 if name == 'previous_applications' else 1,
                'dates': ['date_decision'] if name == 'credit_cases' else [], 'relationship': RELATIONSHIPS.get(name)}
        with open_initial_tables(self.root, self.spark) as (frames, _):
            report = validate_silver_frames(frames, plan,
                {'credit_cases': 2, 'credit_static': 2, 'previous_applications': 3})
        self.assertEqual(report['accepted_rows'], 7)
        history = report['relationships']['previous_applications']
        self.assertEqual((history['orphan_keys'], history['parent_keys_without_match'], history['max_rows_per_covered_case']), (0, 0, 2))
        self.assertEqual(report['relationships']['credit_static']['base_left_join_rows'], 2)


class SilverExecutionIntegrationTests(unittest.TestCase):
    """Fluxo completo com arquivos Bronze e Delta reais, somente dados sintéticos."""

    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        from src.utils.run_context import RunContext
        from src.pipelines.run_bronze_mvp import run_bronze
        from src.bronze.inputs import bind_sample
        from src.pipelines.run_silver_initial import EXECUTION_CODE
        from test_bronze_ingestion import publish_fixture

        cls.spark = create_spark_session(ROOT, app_name='silver-execution-tests', delta=True)
        cls.spark.conf.set('spark.databricks.delta.snapshotPartitions', '2')
        cls.temp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.temp.name) / 'repo'
        cls.repo.mkdir()
        # Configurações mínimas obedecem aos mesmos loaders e hashes do recorte real.
        for name in (*EXECUTION_CODE, 'configs/quality_rules_bronze.yaml', 'configs/paths.yaml',
                     'configs/spark.yaml', 'requirements.lock'):
            target = cls.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        notebook = cls.repo / 'notebooks/analise_silver.ipynb'
        notebook.parent.mkdir()
        notebook.write_text('{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}')
        ctx = RunContext.create(cls.repo)
        selection = publish_fixture(ctx, 'silver-execution', cls.spark)
        snapshot = cls.repo / 'configs/contracts/home_credit_v1.yaml'
        contract = yaml.safe_load(snapshot.read_text())
        for spec in contract['tables'].values():
            spec['grain'] = 'synthetic_fixture'
        snapshot.write_text(yaml.safe_dump(contract))
        sample = ctx.sample_dir / selection
        manifest = json.loads((sample / '_selection.json').read_text())
        manifest['identity']['contract_sha256'] = sha256(snapshot)
        digest = hashlib.sha256(json.dumps(manifest['identity'], sort_keys=True).encode()).hexdigest()
        cls.selection = digest[:24]
        manifest.update(selection_id=cls.selection, identity_sha256=digest)
        (sample / '_selection.json').write_text(json.dumps(manifest))
        sample.rename(ctx.sample_dir / cls.selection)
        policy = yaml.safe_load((ROOT / 'configs/silver_policy_v1.yaml').read_text())
        policy.update(snapshot_contract_sha256=sha256(snapshot), notebook_sha256=sha256(notebook),
            tables={n: {'key': s['key'], 'cast_to_date': ['date_decision'] if n == 'train_base' else []}
                    for n, s in contract['tables'].items()})
        policy_path = cls.repo / 'configs/silver_policy_v1.yaml'
        policy_path.write_text(yaml.safe_dump(policy))
        silver_contract = yaml.safe_load((ROOT / 'configs/contracts/silver_initial_v1.yaml').read_text())
        silver_contract.update(snapshot_contract_sha256=sha256(snapshot), silver_policy_sha256=sha256(policy_path))
        (cls.repo / 'configs/contracts/silver_initial_v1.yaml').write_text(yaml.safe_dump(silver_contract))
        run_bronze(bind_sample(ctx, cls.selection), cls.spark)
        cls.backup = Path(cls.temp.name) / 'backup'
        shutil.copytree(cls.repo, cls.backup)

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        # O template é restaurado no mesmo path; nenhum snapshot JVM da tentativa
        # anterior deve sobreviver à restauração da fixture descartável.
        self.spark._jvm.org.apache.spark.sql.delta.DeltaLog.clearCache()
        shutil.rmtree(self.repo)
        shutil.copytree(self.backup, self.repo)

    def run_pipeline(self, **kwargs):
        from src.pipelines.run_silver_initial import run_silver_initial
        from src.utils.run_context import RunContext
        ctx = RunContext.create(self.repo)
        return run_silver_initial(ctx, self.spark, self.selection, **kwargs)

    def acceptances(self):
        return sorted((self.repo / 'data/silver').rglob('acceptances/*.json'))

    def test_creation_retry_and_explicit_existing_error(self):
        from src.silver.acceptance import verify_acceptance
        first = self.run_pipeline()
        self.assertFalse(first['reused'])
        receipt = verify_acceptance(self.repo, Path(first['acceptance']))
        self.assertEqual({n: t['rows'] for n, t in receipt['tables'].items()},
                         {'credit_cases': 2, 'credit_static': 2, 'previous_applications': 2})
        self.assertEqual({t['version'] for t in receipt['tables'].values()}, {0})
        root = self.repo / receipt['materialization_root']
        before = sha256(root / '_materialization.json')
        retry = self.run_pipeline()
        self.assertTrue(retry['reused'])
        self.assertEqual(first['materialization_id'], retry['materialization_id'])
        self.assertEqual(verify_acceptance(self.repo, Path(retry['acceptance']))['tables'], receipt['tables'])
        self.assertEqual(sha256(root / '_materialization.json'), before)
        receipts = {p: p.read_bytes() for p in self.acceptances()}
        with self.assertRaises(FileExistsError):
            self.run_pipeline(existing='error')
        self.assertEqual({p: p.read_bytes() for p in self.acceptances()}, receipts)
        self.assertEqual(sha256(root / '_materialization.json'), before)
        reports = [json.loads(p.read_text()) for p in (self.repo / 'artifacts/silver_runs').glob('*.json')]
        self.assertEqual(sorted(r['status'] for r in reports), ['failed', 'passed', 'passed'])

    def test_contract_failure_blocks_acceptance_and_retry_reuses_technical_package(self):
        from src.quality.silver_contracts import SilverContractError
        with patch('src.pipelines.run_silver_initial.validate_silver_frames',
                   side_effect=SilverContractError({'status': 'failed', 'checks': [{'success': False}]})):
            with self.assertRaises(SilverContractError):
                self.run_pipeline()
        self.assertFalse(self.acceptances())
        packages = list((self.repo / 'data/silver').rglob('_materialization.json'))
        self.assertEqual(len(packages), 1)
        before = sha256(packages[0])
        self.assertTrue(self.run_pipeline()['reused'])
        self.assertEqual(sha256(packages[0]), before)

    def test_failure_publishing_receipt_preserves_previous_acceptance(self):
        from src.silver.acceptance import _write_once, verify_acceptance
        first = self.run_pipeline()
        previous = Path(first['acceptance']).read_bytes()

        def interrupt_receipt(path, value):
            if path.parent.name == 'acceptances':
                raise OSError('simulated failure before acceptance')
            return _write_once(path, value)

        with patch('src.silver.acceptance._write_once', side_effect=interrupt_receipt):
            with self.assertRaises(OSError):
                self.run_pipeline()
        self.assertEqual(len(self.acceptances()), 1)
        self.assertEqual(Path(first['acceptance']).read_bytes(), previous)
        verify_acceptance(self.repo, Path(first['acceptance']))
        self.assertTrue(self.run_pipeline()['reused'])
        self.assertEqual(len(self.acceptances()), 2)

    def test_configuration_change_during_validation_blocks_acceptance(self):
        from src.quality.silver_contracts import validate_silver_frames

        def mutate_after_contracts(*args, **kwargs):
            result = validate_silver_frames(*args, **kwargs)
            path = self.repo / 'configs/spark.yaml'
            path.write_text(path.read_text() + '\n# simulated configuration mutation\n')
            return result

        with patch('src.pipelines.run_silver_initial.validate_silver_frames', side_effect=mutate_after_contracts):
            with self.assertRaisesRegex(RuntimeError, 'configuração mudou'):
                self.run_pipeline()
        self.assertFalse(self.acceptances())

    def test_missing_bronze_gate_and_concurrent_writer_do_not_accept(self):
        from src.bronze.build_bronze import _ingestion_lock
        gate = self.repo / 'data/bronze/samples' / self.selection / '_READY.json'
        original = gate.read_bytes()
        gate.unlink()
        with self.assertRaises(ValueError):
            self.run_pipeline()
        self.assertFalse(self.acceptances())
        gate.write_bytes(original)
        parent = self.repo / 'data/silver/samples' / self.selection
        with _ingestion_lock(parent, '.silver_pipeline.lock'):
            with self.assertRaises(OSError):
                self.run_pipeline()
        self.assertFalse(self.acceptances())
        self.assertFalse(list(parent.rglob('_materialization.json')))

    def test_modified_receipt_report_or_package_is_rejected(self):
        from src.silver.acceptance import verify_acceptance
        result = self.run_pipeline()
        receipt_path = Path(result['acceptance'])
        receipt = json.loads(receipt_path.read_text())
        receipt_path.write_text(json.dumps({**receipt, 'selection_id': 'f' * 24}))
        with self.assertRaises(ValueError):
            verify_acceptance(self.repo, receipt_path)
        receipt_path.write_text(json.dumps(receipt))
        report_path = Path(result['report'])
        original = report_path.read_bytes()
        report_path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Relatório de aceite alterado'):
            verify_acceptance(self.repo, receipt_path)
        report_path.write_bytes(original)
        file = next((self.repo / receipt['materialization_root']).rglob('*.parquet'))
        file.unlink()
        with self.assertRaisesRegex(ValueError, 'Pacote Delta mudou'):
            verify_acceptance(self.repo, receipt_path)


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (InitialDeltaIntegrationTests, SilverExecutionIntegrationTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
