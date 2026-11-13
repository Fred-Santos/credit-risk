"""Protocolo de entrada e recuperação com arquivos Spark sintéticos reais."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml
from unittest.mock import patch

from src.bronze.inputs import bind_sample, bind_raw
from src.pipelines.download_home_credit import sha256
from src.utils.run_context import RunContext

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {'train_base': 2, 'train_static_0': 2, 'train_applprev_1': 2}


def publish_fixture(ctx, label, spark=None):
    """Snapshot mínimo de teste; emula manifesto do produtor, sem dados Kaggle."""
    contract = ctx.repo_root / 'configs/contracts/home_credit_v1.yaml'
    contract.parent.mkdir(parents=True, exist_ok=True)
    rows = {
        'train_base': ([(101, '2020-01-01', 202001, 0, 0), (102, '2020-01-02', 202001, 1, 1)],
                       'case_id long, date_decision string, MONTH long, WEEK_NUM long, target long'),
        'train_static_0': ([(101, 1.5), (102, None)], 'case_id long, amount double'),
        'train_applprev_1': ([(101, 0, 5.0), (101, 1, 6.0)], 'case_id long, num_group1 long, amount double'),
    }
    # Contrato mínimo válido: mesmos princípios do real, com schemas das fixtures.
    schemas = {
        'train_base': {'case_id': 'bigint', 'date_decision': 'string', 'MONTH': 'bigint', 'WEEK_NUM': 'bigint', 'target': 'bigint'},
        'train_static_0': {'case_id': 'bigint', 'amount': 'double'},
        'train_applprev_1': {'case_id': 'bigint', 'num_group1': 'bigint', 'amount': 'double'},
    }
    tables = {}
    sources = {}
    for name, schema in schemas.items():
        filename = f'{name}.parquet'
        sources[filename] = {'sha256': '0' * 64, 'bytes': 0}
        if spark is not None:
            import shutil
            temporary = ctx.raw_dir / f'.fixture_{name}'
            values, spark_schema = rows[name]
            spark.createDataFrame(values, spark_schema).coalesce(1).write.parquet(str(temporary))
            raw_file = ctx.raw_dir / filename
            shutil.copyfile(next(temporary.glob('*.parquet')), raw_file)
            shutil.rmtree(temporary)
            sources[filename] = {'sha256': sha256(raw_file), 'bytes': raw_file.stat().st_size}
        key = ['case_id', 'num_group1'] if name == 'train_applprev_1' else ['case_id']
        tables[name] = {'schema': schema, 'key': key, 'required_non_null': list(schema) if name == 'train_base' else key,
                        'minimum_rows': 0 if name == 'train_applprev_1' else 1, 'files': [filename]}
        if name != 'train_base':
            tables[name]['reference'] = {'table': 'train_base', 'columns': ['case_id'],
                                         'full_coverage': name == 'train_static_0'}
    contract.write_text(yaml.safe_dump({'version': 1, 'sources': sources, 'tables': tables}))
    identity = {'contract_sha256': sha256(contract), 'synthetic_fixture': label}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    selection_id = digest[:24]
    sample = ctx.sample_dir / selection_id
    for name, (values, schema) in rows.items():
        path = sample / 'parquet_files/train' / name
        if spark is None:
            path.mkdir(parents=True)
            (path / 'fixture.parquet').write_bytes(b'synthetic-protocol-fixture')
        else:
            spark.createDataFrame(values, schema).coalesce(1).write.parquet(str(path))
    files = {p.relative_to(sample).as_posix(): sha256(p) for p in sample.rglob('*.parquet')}
    validation = {'status': 'passed', 'checks': [{'success': True}]}
    (sample / '_selection.json').write_text(json.dumps({
        'identity': identity, 'identity_sha256': digest, 'selection_id': selection_id,
        'output_checksums': files, 'case_count': 2, 'counts': COUNTS,
        'source_validation': validation, 'sample_validation': validation}))
    return selection_id


class BronzeInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = RunContext.create(Path(self.temp.name))

    def test_sample_binding_preserves_raw_and_isolates_namespaces(self):
        a = bind_sample(self.ctx, publish_fixture(self.ctx, 'a'))
        b = bind_sample(self.ctx, publish_fixture(self.ctx, 'b'))
        self.assertEqual(a.ctx.raw_dir, self.ctx.raw_dir)
        self.assertNotEqual(a.ctx.ingestion_dir, a.ctx.raw_dir)
        self.assertNotEqual(a.ctx.bronze_dir, b.ctx.bronze_dir)
        self.assertNotEqual(a.ctx.docs_root, b.ctx.docs_root)
        self.assertNotEqual(bind_raw(self.ctx).ctx.bronze_dir, a.ctx.bronze_dir)

    def test_invalid_identifier_and_unapproved_input_are_rejected(self):
        with self.assertRaises(ValueError):
            bind_sample(self.ctx, '../escape')
        selection_id = publish_fixture(self.ctx, 'invalid')
        path = self.ctx.sample_dir / selection_id / '_selection.json'
        manifest = json.loads(path.read_text())
        manifest['sample_validation']['status'] = 'failed'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'não aprovado'):
            bind_sample(self.ctx, selection_id)

    def test_modified_input_is_rejected_before_ingestion(self):
        selection_id = publish_fixture(self.ctx, 'modified')
        next((self.ctx.sample_dir / selection_id).rglob('*.parquet')).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'alterado'):
            bind_sample(self.ctx, selection_id)


@contextmanager
def lock_in_child(path):
    code = ('import fcntl,sys; '
            'handle=open(sys.argv[1],"a+b"); '
            'fcntl.flock(handle,fcntl.LOCK_EX); '
            'print("locked",flush=True); sys.stdin.read(1)')
    process = subprocess.Popen([sys.executable, '-c', code, str(path)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        if process.stdout.readline().strip() != 'locked':
            raise RuntimeError('Processo auxiliar não adquiriu o lock')
        yield
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


@unittest.skipUnless(importlib.util.find_spec('pyspark'), 'PySpark não instalado')
class BronzeRecoverySparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        cls.spark = create_spark_session(ROOT, app_name='bronze-recovery-tests')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = RunContext.create(self.root)
        configs = self.root / 'configs'
        configs.mkdir()
        self.rules = configs / 'quality_rules_bronze.yaml'
        self.valid_rules = (ROOT / 'configs/quality_rules_bronze.yaml').read_text(encoding='utf-8-sig')
        self.rules.write_text(self.valid_rules)
        self.selection_id = publish_fixture(self.ctx, 'spark', self.spark)

    def bound(self):
        return bind_sample(RunContext.create(self.root), self.selection_id)

    def run_pipeline(self, bound=None):
        from src.pipelines.run_bronze_mvp import run_bronze
        return run_bronze(bound or self.bound(), self.spark)

    def test_first_load_repeat_and_original_metadata(self):
        first = self.bound()
        before = {p: sha256(p) for p in first.ctx.ingestion_dir.rglob('*.parquet')}
        report = self.run_pipeline(first)
        self.assertEqual(report['counts'], COUNTS)
        repeat = self.bound()
        self.assertNotEqual(first.ctx.run_id, repeat.ctx.run_id)
        self.assertEqual(self.run_pipeline(repeat)['written_datasets'], [])
        ready = json.loads((repeat.ctx.bronze_dir / '_READY.json').read_text())
        self.assertEqual(ready['verified_by_run_id'], repeat.ctx.run_id)
        for name in COUNTS:
            frame = self.spark.read.parquet(str(repeat.ctx.bronze_dir / name))
            self.assertEqual({r._run_id for r in frame.select('_run_id').distinct().collect()}, {first.ctx.run_id})
            self.assertEqual(dict(frame.dtypes)['_ingest_date'], 'date')
            self.assertTrue(all(self.selection_id in r._source_file for r in frame.select('_source_file').distinct().collect()))
        self.assertEqual(before, {p: sha256(p) for p in before})

    def test_real_write_failure_is_not_published_and_retry_skips_commits(self):
        from pyspark.sql.readwriter import DataFrameWriter
        original = DataFrameWriter.parquet
        first = self.bound()
        def fail_after_write(writer, path, *args, **kwargs):
            result = original(writer, path, *args, **kwargs)
            if '/.staging/train_base/' in str(path):
                raise RuntimeError('injected failure after Spark write')
            return result
        with patch.object(DataFrameWriter, 'parquet', fail_after_write):
            with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                self.run_pipeline(first)
        root = first.ctx.bronze_dir
        self.assertFalse((root / '_READY.json').exists())
        self.assertEqual(list((root / 'train_base').rglob('*.parquet')), [])
        self.assertTrue(list((root / 'train_applprev_1').rglob('*.parquet')))
        report = self.run_pipeline()
        self.assertEqual(report['counts'], COUNTS)
        self.assertEqual(len(report['written_datasets']), 2)
        self.assertEqual(list((root / '.staging').rglob('*.parquet')), [])

    def test_interruption_after_rename_recovers_without_duplicate(self):
        original = Path.rename
        first = self.bound()
        def publish_then_interrupt(path, destination):
            result = original(path, destination)
            if '.staging' in path.parts and Path(destination).name.startswith('ingest_batch='):
                raise RuntimeError('injected interruption after publish')
            return result
        with patch.object(Path, 'rename', publish_then_interrupt):
            with self.assertRaisesRegex(RuntimeError, 'after publish'):
                self.run_pipeline(first)
        self.assertFalse((first.ctx.bronze_dir / '_READY.json').exists())
        report = self.run_pipeline()
        self.assertEqual(report['counts'], COUNTS)
        self.assertEqual(len(report['written_datasets']), 2)
        frame = self.spark.read.parquet(str(first.ctx.bronze_dir / 'train_applprev_1'))
        self.assertEqual({r._run_id for r in frame.select('_run_id').distinct().collect()}, {first.ctx.run_id})

    def test_real_quality_failure_blocks_ready_and_retry_recovers(self):
        import yaml
        rules = yaml.safe_load(self.valid_rules)
        rules['tables'].append({'pattern': 'train_base', 'checks': [
            {'type': 'require_columns', 'columns': ['invalid_fixture_requirement']}]})
        self.rules.write_text(yaml.safe_dump(rules))
        bound = self.bound()
        with self.assertRaisesRegex(RuntimeError, 'Data Quality'):
            self.run_pipeline(bound)
        self.assertFalse((bound.ctx.bronze_dir / '_READY.json').exists())
        reports = list((bound.ctx.docs_root / 'runs').glob('*.json'))
        self.assertEqual(json.loads(reports[0].read_text())['status'], 'failed')
        self.rules.write_text(self.valid_rules)
        retry = self.run_pipeline()
        self.assertEqual(retry['written_datasets'], [])
        self.assertEqual(retry['counts'], COUNTS)

    @unittest.skipIf(sys.platform == 'win32', 'Protocolo POSIX Linux/WSL')
    def test_other_process_lock_blocks_writer_and_death_releases_it(self):
        from src.bronze.build_bronze import build_bronze_from_raw
        bound = self.bound()
        root = bound.ctx.bronze_dir
        root.mkdir(parents=True)
        with lock_in_child(root / '.pipeline.lock'):
            with self.assertRaises(BlockingIOError):
                self.run_pipeline(bound)
        with lock_in_child(root / '.ingestion.lock'):
            with self.assertRaises(BlockingIOError):
                build_bronze_from_raw(bound.ctx, self.spark)
        self.assertEqual(list(root.rglob('*.parquet')), [])
        self.assertEqual(self.run_pipeline()['counts'], COUNTS)

    def test_changed_committed_output_blocks_retry_without_overwrite(self):
        bound = self.bound()
        self.run_pipeline(bound)
        path = next(bound.ctx.bronze_dir.rglob('*.parquet'))
        path.write_bytes(b'corrupted-fixture')
        with self.assertRaisesRegex(RuntimeError, 'Saída Bronze alterada'):
            self.run_pipeline()
        self.assertEqual(path.read_bytes(), b'corrupted-fixture')
        self.assertFalse((bound.ctx.bronze_dir / '_READY.json').exists())
