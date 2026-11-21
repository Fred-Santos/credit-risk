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


class SparkProfileSelectionTests(unittest.TestCase):
    def test_default_and_expansion_profiles_have_distinct_heap(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(load_spark_settings(root/'configs/spark.yaml')['config']['spark.driver.memory'], '2g')
        self.assertEqual(load_spark_settings(root/'configs/spark_expansion.yaml')['config']['spark.driver.memory'], '8g')

    def test_explicit_profile_rejects_existing_context(self):
        from unittest.mock import patch
        from src.utils.spark import session_settings
        with patch('pyspark.SparkContext._active_spark_context', object()):
            with self.assertRaisesRegex(RuntimeError, 'novo processo'):
                session_settings(Path('.'), Path('configs/spark_expansion.yaml'))

    def test_explicit_profile_rejects_jvm_from_stopped_context(self):
        from unittest.mock import patch
        from src.utils.spark import session_settings
        with patch('pyspark.SparkContext._active_spark_context', None), \
                patch('pyspark.SparkContext._gateway', object()):
            with self.assertRaisesRegex(RuntimeError, 'novo processo'):
                session_settings(Path('.'), Path('configs/spark_expansion.yaml'))
