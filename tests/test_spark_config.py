import tempfile
from pathlib import Path
import unittest

from src.utils.spark import load_spark_settings


class SparkConfigurationTests(unittest.TestCase):
    def load(self, content):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "spark.yaml"
            path.write_text(content)
            return load_spark_settings(path)

    def test_custom_values_are_preserved(self):
        settings = self.load("spark:\n  master: local[1]\n  app_name: custom\n"
                             "  config:\n    spark.sql.shuffle.partitions: '1'\n")
        self.assertEqual(settings["master"], "local[1]")
        self.assertEqual(settings["config"]["spark.sql.shuffle.partitions"], "1")

    def test_invalid_configuration_fails_explicitly(self):
        for content in ["[]", "spark: []", "spark: {master: '', app_name: x}",
                        "spark: {master: 'local[1]', app_name: x, typo: true}",
                        "spark: {master: 'local[1]', app_name: x, config: {wrong: '1'}}",
                        "spark: {master: 'local[1]', app_name: x, config: {spark.x: 1}}"]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.load(content)
