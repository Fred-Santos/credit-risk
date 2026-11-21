"""Configuração compartilhada; importar este módulo não inicia uma JVM."""
from __future__ import annotations

from pathlib import Path

import yaml


def load_spark_settings(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or set(document) != {"spark"}:
        raise ValueError("Configuração deve conter somente a seção spark")
    settings = document["spark"]
    if not isinstance(settings, dict) or set(settings) - {"master", "app_name", "config"}:
        raise ValueError("Chaves inválidas na configuração Spark")
    for key in ("master", "app_name"):
        if not isinstance(settings.get(key), str) or not settings[key].strip():
            raise ValueError(f"spark.{key} deve ser uma string não vazia")
    options = settings.get("config", {})
    if not isinstance(options, dict):
        raise ValueError("spark.config deve ser um mapeamento")
    for key, value in options.items():
        if not isinstance(key, str) or not key.startswith("spark."):
            raise ValueError("Opções devem começar com spark.")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Valor de {key} deve ser uma string não vazia")
        if key in {"spark.master", "spark.app.name"}:
            raise ValueError(f"Use master/app_name em vez de {key}")
    return settings


def create_spark_session(repo_root: Path, *, app_name: str | None = None,
                         delta: bool = False, config_path: Path | None = None):
    from pyspark.sql import SparkSession

    settings = session_settings(repo_root, config_path)
    builder = (SparkSession.builder.master(settings["master"])
               .appName(app_name or settings["app_name"]))
    for key, value in settings.get("config", {}).items():
        builder = builder.config(key, value)
    if delta:
        from delta import configure_spark_with_delta_pip
        builder = (builder
                   .config("spark.jars.ivy", str(repo_root / ".runtime" / "ivy"))
                   .config("spark.jars.ivySettings", str(repo_root / "configs" / "ivysettings.xml"))
                   .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                   .config("spark.sql.catalog.spark_catalog",
                           "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
        builder = configure_spark_with_delta_pip(builder)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def session_settings(repo_root: Path, config_path: Path | None = None) -> dict:
    """Perfil explícito exige JVM nova; getOrCreate não redimensiona heap existente."""
    if config_path is not None:
        from pyspark import SparkContext
        if (SparkContext._active_spark_context is not None
                or SparkContext._gateway is not None):
            raise RuntimeError('Perfil explícito requer novo processo Spark, sem contexto ativo')
    path = Path(config_path) if config_path is not None else Path('configs/spark.yaml')
    return load_spark_settings(path if path.is_absolute() else repo_root / path)
