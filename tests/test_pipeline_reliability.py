"""Testes sem JVM: transações locais e contratos de qualidade com doubles Spark."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from src.quality import engine
from src.utils.run_context import RunContext

# Permite testar a transação de arquivos sem instalar Spark/JVM.
stubs = {name: types.ModuleType(name) for name in
         ['pyspark', 'pyspark.sql', 'pyspark.sql.functions']}
stubs['pyspark.sql'].SparkSession = object
stubs['pyspark.sql'].DataFrame = object
for name in ['current_date', 'input_file_name', 'lit']:
    setattr(stubs['pyspark.sql.functions'], name, lambda *args: None)
# Carrega uma cópia privada: não deixa o módulo produtivo com imports falsos
# no cache de sys.modules quando a integração real roda no mesmo processo.
spec = importlib.util.spec_from_file_location(
    '_bronze_unit_double', Path(__file__).resolve().parents[1] / 'src/bronze/build_bronze.py')
bronze = importlib.util.module_from_spec(spec)
with patch.dict('sys.modules', stubs):
    spec.loader.exec_module(bronze)


class Frame:
    columns = ['case_id']
    dtypes = [('case_id', 'bigint')]

    def __init__(self, rows=1, fail=False):
        self.rows, self.fail = rows, fail

    def limit(self, size):
        return Frame(min(size, self.rows))

    def count(self):
        return self.rows

    def coalesce(self, size):
        return self

    @property
    def write(self):
        return self

    def mode(self, mode):
        return self

    def parquet(self, destination):
        path = Path(destination)
        path.mkdir(parents=True)
        (path / 'part-000.parquet').write_bytes(b'parquet')
        if self.fail:
            raise RuntimeError('simulated write failure')
        (path / '_SUCCESS').touch()


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = RunContext.create(self.root)
        self.train = self.ctx.raw_dir / 'parquet_files' / 'train'
        self.train.mkdir(parents=True)
        self.spark = types.SimpleNamespace(read=types.SimpleNamespace(parquet=lambda *args: Frame()))
        self.add_columns = patch.object(bronze, '_add_bronze_columns', lambda df, run: df)
        self.add_columns.start()
        self.addCleanup(self.add_columns.stop)

    def source(self, name='train_base.parquet', content=b'source'):
        path = self.train / name
        path.write_bytes(content)
        return path

    def build(self, **kwargs):
        return bronze.build_bronze_from_raw(self.ctx, self.spark, **kwargs)

    def test_repeat_and_changed_chunk_size_do_not_duplicate(self):
        self.source()
        self.assertEqual(len(self.build()), 1)
        self.ctx = RunContext.create(self.root)
        self.assertEqual(self.build(max_files_per_read=1), [])
        self.assertEqual(len(list((self.root / 'data/bronze').rglob('part-*.parquet'))), 1)

    def test_failure_is_not_published_and_retry_recovers(self):
        self.source()
        self.spark.read.parquet = lambda *args: Frame(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            self.build()
        self.assertEqual(list((self.root / 'data/bronze/train_base').rglob('*.parquet')), [])
        self.spark.read.parquet = lambda *args: Frame()
        self.assertEqual(len(self.build()), 1)

    def test_partial_dataset_retry_skips_committed_source(self):
        nested = self.train / 'train_base'
        nested.mkdir()
        (nested / 'a.parquet').write_bytes(b'a')
        (nested / 'b.parquet').write_bytes(b'b')
        self.spark.read.parquet = lambda name: Frame(fail=name.endswith('b.parquet'))
        with self.assertRaises(RuntimeError):
            self.build()
        calls = []
        def read(name):
            calls.append(name)
            return Frame()
        self.spark.read.parquet = read
        self.build()
        self.assertEqual([Path(p).name for p in calls], ['b.parquet'])
        self.assertEqual(len(list((self.root / 'data/bronze/train_base').rglob('part-*.parquet'))), 2)

    def test_changed_source_rejected(self):
        path = self.source()
        self.build()
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'alterada'):
            self.build()

    def test_failure_after_publish_is_safe_to_retry(self):
        self.source()
        rename = Path.rename
        def publish_then_fail(path, destination):
            rename(path, destination)
            raise RuntimeError('process stopped after publish')
        with patch.object(Path, 'rename', publish_then_fail):
            with self.assertRaisesRegex(RuntimeError, 'after publish'):
                self.build()
        self.assertEqual(self.build(), [])
        self.assertEqual(len(list((self.root / 'data/bronze').rglob('part-*.parquet'))), 1)

    @unittest.skipIf(__import__('os').name == 'nt', 'Teste de flock POSIX')
    def test_concurrent_build_is_rejected(self):
        self.source()
        root = self.root / 'data/bronze'
        root.mkdir()
        with bronze._ingestion_lock(root):
            with self.assertRaises(BlockingIOError):
                self.build()
        self.assertEqual(len(self.build()), 1)

    def test_legacy_bronze_rejected(self):
        self.source()
        path = self.root / 'data/bronze/train_base'
        path.mkdir(parents=True)
        (path / 'old.parquet').touch()
        with self.assertRaisesRegex(RuntimeError, 'legada'):
            self.build()

    def test_flat_and_nested_inputs_both_discovered(self):
        self.source()
        nested = self.train / 'nested'
        nested.mkdir()
        (nested / 'a.parquet').touch()
        self.assertEqual(len(bronze._discover_inputs(self.train)), 2)

    def test_empty_raw_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Nenhum parquet'):
            self.build()

    def quality_config(self, checks, default='warn'):
        config = self.root / 'configs'
        config.mkdir(exist_ok=True)
        (config / 'quality_rules.yaml').write_text(json.dumps({
            'defaults': {'action_on_fail': default},
            'tables': [{'pattern': '*', 'checks': checks}]}))

    def test_explicit_fail_overrides_warn_default_and_saves_report(self):
        self.source()
        self.quality_config([{'type': 'require_columns', 'columns': ['target'], 'severity': 'fail'}])
        with self.assertRaisesRegex(RuntimeError, 'Data Quality'):
            engine.run_checks(self.ctx, self.spark, layer='raw')
        report = next((self.root / 'docs/data_quality/results').glob('*.json'))
        self.assertEqual(json.loads(report.read_text())['failed_checks'], 1)

    def test_explicit_warn_does_not_block_fail_default(self):
        self.source()
        self.quality_config([{'type': 'require_columns', 'columns': ['target'], 'severity': 'warn'}], 'fail')
        result = engine.run_checks(self.ctx, self.spark, layer='raw')
        self.assertEqual(result['failed_checks'], 0)
        self.assertEqual(result['warning_checks'], 1)

    def test_empty_layer_fails(self):
        self.quality_config([{'type': 'non_empty'}])
        with self.assertRaises(RuntimeError):
            engine.run_checks(self.ctx, self.spark, layer='raw')

    def test_unknown_check_is_configuration_error_even_with_warn(self):
        self.quality_config([{'type': 'typo', 'severity': 'warn'}])
        with self.assertRaisesRegex(ValueError, 'desconhecido'):
            engine.run_checks(self.ctx, self.spark, layer='raw')

    def test_type_and_missing_column_checks(self):
        self.assertFalse(engine.evaluate(Frame(), {'type': 'column_types', 'types': {'case_id': 'string'}}, self.spark, self.root)['success'])
        self.assertFalse(engine.evaluate(Frame(), {'type': 'not_null', 'columns': ['missing']}, self.spark, self.root)['success'])

    def test_shard_number_does_not_change_key_depth(self):
        rules = engine.load_rules(Path('configs/quality_rules_bronze.yaml'))
        for name, expected in [('train_credit_bureau_a_2_0', ['case_id', 'num_group1', 'num_group2']),
                               ('train_credit_bureau_a_1_2', ['case_id', 'num_group1']),
                               ('train_static_0_1', ['case_id'])]:
            unique = [c['columns'] for c in engine.match_rules(rules, name) if c['type'] == 'unique']
            self.assertEqual(unique, [expected])

    def test_bronze_reads_dataset_root_not_individual_parts(self):
        self.source()
        self.build()
        config = self.root / 'configs'
        config.mkdir()
        (config / 'quality_rules_bronze.yaml').write_text(json.dumps({
            'required_datasets': ['train_base'],
            'tables': [{'pattern': '*', 'checks': [{'type': 'non_empty'}]}]}))
        calls = []
        def read(name):
            calls.append(Path(name))
            return Frame()
        self.spark.read.parquet = read
        engine.run_checks(self.ctx, self.spark, layer='bronze')
        self.assertEqual(calls, [self.root / 'data/bronze/train_base'])


if __name__ == '__main__':
    unittest.main()
