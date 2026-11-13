from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.pipelines import download_home_credit as acquisition


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / "raw"

    def fetch(self, remote, stage):
        path = stage / remote
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"controlled-test-payload")

    def test_retry_checks_source_without_downloading_again(self):
        acquisition.download_selected(self.raw, ["train/base.parquet"], fetch=self.fetch)
        with patch.object(acquisition, "_fetch", side_effect=AssertionError("network forbidden")):
            result = acquisition.download_selected(self.raw, ["train/base.parquet"],
                                                   fetch=lambda *args: self.fail("download repetido"))
        self.assertEqual(result[0]["status"], "complete")

    def test_failure_after_publish_recovers_journal(self):
        write_record = acquisition._write_record
        def interrupted(path, record):
            if record["status"] == "complete":
                raise RuntimeError("interrupted after publish")
            write_record(path, record)
        with patch.object(acquisition, "_write_record", interrupted):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                acquisition.download_selected(self.raw, ["base.parquet"], fetch=self.fetch)
        result = acquisition.download_selected(self.raw, ["base.parquet"],
                                               fetch=lambda *args: self.fail("download repetido"))
        self.assertEqual(result[0]["status"], "complete")

    def test_modified_source_is_preserved_and_rejected(self):
        acquisition.download_selected(self.raw, ["base.parquet"], fetch=self.fetch)
        (self.raw / "base.parquet").write_bytes(b"modified")
        with self.assertRaisesRegex(RuntimeError, "divergente"):
            acquisition.download_selected(self.raw, ["base.parquet"], fetch=self.fetch)
        self.assertEqual((self.raw / "base.parquet").read_bytes(), b"modified")

    def test_partial_download_is_not_published(self):
        def interrupted(remote, stage):
            self.fetch(remote, stage)
            raise RuntimeError("network failed")
        with self.assertRaises(RuntimeError):
            acquisition.download_selected(self.raw, ["base.parquet"], fetch=interrupted)
        self.assertFalse((self.raw / "base.parquet").exists())
        self.assertEqual(list(self.raw.glob(".download-*")), [])

    def test_unexpected_archive_member_is_not_extracted(self):
        def malicious(remote, stage):
            with zipfile.ZipFile(stage / "payload.zip", "w") as bundle:
                bundle.writestr("../outside", "test")
        with self.assertRaisesRegex(RuntimeError, "Conteúdo ZIP"):
            acquisition.download_selected(self.raw, ["base.parquet"], fetch=malicious)
        self.assertFalse((self.raw.parent / "outside").exists())

    def test_safe_single_file_archive_is_supported(self):
        def compressed(remote, stage):
            with zipfile.ZipFile(stage / "payload.zip", "w") as bundle:
                bundle.writestr(remote, "test")
        acquisition.download_selected(self.raw, ["train/base.parquet"], fetch=compressed)
        self.assertEqual((self.raw / "train/base.parquet").read_text(), "test")

    def test_api_error_and_timeout_are_diagnosed_without_raw_response(self):
        with patch.object(acquisition.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 1, stdout='private-response', stderr='')) as call:
            with self.assertRaisesRegex(RuntimeError, 'autenticação') as error:
                acquisition._fetch('base.parquet', self.raw)
            self.assertNotIn('private-response', str(error.exception))
            self.assertIn('--file', call.call_args.args[0])
        with patch.object(acquisition.subprocess, 'run', side_effect=subprocess.TimeoutExpired('kaggle', 600)):
            with self.assertRaisesRegex(RuntimeError, 'Tempo limite'):
                acquisition._fetch('base.parquet', self.raw)
