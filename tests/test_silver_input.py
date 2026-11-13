"""Gate, arquivos, união estrita e lock do leitor Silver; sem dados Kaggle."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.bronze.inputs import bind_sample
from src.pipelines.download_home_credit import sha256
from src.silver.read_bronze import open_bronze_snapshot, verify_approval, _index
from src.utils.run_context import RunContext
from test_bronze_ingestion import publish_fixture

ROOT = Path(__file__).resolve().parents[1]


class SilverInputSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.utils.spark import create_spark_session
        from src.pipelines.run_bronze_mvp import run_bronze
        cls.spark = create_spark_session(ROOT, app_name='silver-input-tests')
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / 'repo'
        cls.root.mkdir()
        (cls.root / 'configs').mkdir()
        (cls.root / 'configs/quality_rules_bronze.yaml').write_text((ROOT / 'configs/quality_rules_bronze.yaml').read_text())
        ctx = RunContext.create(cls.root)
        cls.selection = publish_fixture(ctx, 'silver-input', cls.spark)
        cls.bound = bind_sample(ctx, cls.selection)
        cls.approval_run = run_bronze(cls.bound, cls.spark)
        cls.backup = Path(cls.temp.name) / 'backup'
        shutil.copytree(cls.root, cls.backup)

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        shutil.rmtree(self.root)
        shutil.copytree(self.backup, self.root)
        self.bound = bind_sample(RunContext.create(self.root), self.selection)
        self.ctx = self.bound.ctx
        self.gate_path = self.ctx.bronze_dir / '_READY.json'

    def update_json(self, path, update):
        value = json.loads(path.read_text())
        update(value)
        path.write_text(json.dumps(value))

    def test_valid_read_preserves_values_and_holds_writer_lock(self):
        from src.bronze.build_bronze import _ingestion_lock
        with open_bronze_snapshot(self.bound, self.spark) as loaded:
            values = sorted((row.case_id, row.amount) for row in loaded.frames['train_static_0'].select('case_id', 'amount').collect())
            self.assertEqual(values, [(101, 1.5), (102, None)])
            self.assertEqual(set(loaded.frames), {'train_base', 'train_static_0', 'train_applprev_1'})
            with self.assertRaises(OSError):
                with _ingestion_lock(self.ctx.bronze_dir, '.pipeline.lock'):
                    pass
        with _ingestion_lock(self.ctx.bronze_dir, '.pipeline.lock'):
            pass  # Liberado após o consumo.

    def test_missing_gate_blocks(self):
        self.gate_path.unlink()
        with self.assertRaises(ValueError):
            verify_approval(self.bound)

    def test_changed_or_extra_file_blocks(self):
        extra = self.ctx.bronze_dir / 'extra.parquet'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'extras ou alterados'):
            verify_approval(self.bound)
        extra.unlink()
        file = next(self.ctx.bronze_dir.rglob('*.parquet'))
        file.unlink()
        with self.assertRaisesRegex(ValueError, 'ausentes'):
            verify_approval(self.bound)

    def test_report_corruption_and_rejected_gate_block(self):
        path = Path(self.approval_run['quality']['json'])
        original = path.read_bytes()
        path.write_text('{}')
        with self.assertRaises(ValueError):
            verify_approval(self.bound)
        path.write_bytes(original)
        self.update_json(self.gate_path, lambda v: v.update(status='failed'))
        with self.assertRaises(ValueError):
            verify_approval(self.bound)

    def test_wrong_selection_and_path_escape_block(self):
        self.update_json(self.gate_path, lambda v: v['input'].update(selection_id='b' * 24))
        with self.assertRaises(ValueError):
            verify_approval(self.bound)
        shutil.copyfile(self.backup / self.gate_path.relative_to(self.root), self.gate_path)
        self.update_json(self.gate_path, lambda v: v.update(run_report='../outside.json'))
        with self.assertRaises(ValueError):
            verify_approval(self.bound)

    def test_configuration_change_requires_reapproval(self):
        path = self.root / 'configs/quality_rules_bronze.yaml'
        path.write_text(path.read_text() + '\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'revalidar Bronze'):
            verify_approval(self.bound)

    def test_change_during_consumer_action_detected_on_exit(self):
        with self.assertRaises(ValueError):
            with open_bronze_snapshot(self.bound, self.spark):
                self.update_json(self.gate_path, lambda v: v.update(status='failed'))

    def reseal_for_negative_test(self):
        # Cria um envelope coerente de teste para exercitar a validação independente
        # do leitor; não simula uma revalidação legítima dos dados pela Bronze.
        from src.bronze.build_bronze import _output_checksums
        for path in self.ctx.bronze_dir.rglob('_ingestion.json'):
            self.update_json(path, lambda v: v.update(output_files=_output_checksums(path.parent)))
        index = _index(self.ctx.bronze_dir)
        self.update_json(self.gate_path, lambda v: v.update(output_checksums=index))
        lineage = Path(self.approval_run['lineage']['json'])
        def update_lineage(value):
            value['artifacts']['bronzeFiles']['files'] = [
                {'path': (self.ctx.bronze_dir / name).relative_to(self.root).as_posix(), 'sha256': digest}
                for name, digest in index.items()]
        self.update_json(lineage, update_lineage)

    def replace_static_shards(self, *, missing_column=False):
        batch = next((self.ctx.bronze_dir / 'train_static_0').glob('ingest_batch=*'))
        source = self.spark.read.parquet(str(batch))
        rows = source.collect()
        schema = source.schema
        for file in batch.glob('*.parquet'):
            file.unlink()
        for file in batch.glob('.*.crc'):
            file.unlink()
        for i in range(2):
            # Duas partes com a mesma chave; o conjunto global tem duplicata.
            frame = self.spark.createDataFrame([rows[0]], schema)
            if missing_column and i == 1:
                frame = frame.drop('amount')
            stage = self.root / f'stage_{i}'
            frame.write.parquet(str(stage))
            next(stage.glob('*.parquet')).replace(batch / f'part-{i}.parquet')
        self.reseal_for_negative_test()

    def test_duplicate_across_shards_blocks_after_union(self):
        self.replace_static_shards()
        with self.assertRaisesRegex(ValueError, 'após união'):
            with open_bronze_snapshot(self.bound, self.spark):
                pass

    def test_missing_column_in_one_shard_not_filled_with_null(self):
        self.replace_static_shards(missing_column=True)
        with self.assertRaisesRegex(ValueError, 'Schema incompatível'):
            with open_bronze_snapshot(self.bound, self.spark):
                pass
