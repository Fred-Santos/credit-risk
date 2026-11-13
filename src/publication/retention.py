"""Retenção auditável; limpeza destrutiva limitada a uma fixture criada aqui."""
from pathlib import Path
import tempfile

from src.publication.protocol import verify_manifest


def audit_retention(repo: Path, registry: Path, spark):
    records = []
    for path in sorted((registry / 'manifests').glob('*.json')):
        manifest, _ = verify_manifest(repo, registry, path.stem, spark)
        if manifest['retention'] != {'minimum_days': 30, 'all_publications_pinned': True, 'real_vacuum': 'forbidden'}:
            raise ValueError('Retenção publicada incompatível')
        for entry in manifest['tables'].values():
            # Prova que a versão inicial da tabela também permanece legível.
            spark.read.format('delta').option('versionAsOf', 0).load(str(repo / entry['path'])).count()
        records.append({'publication_id': path.stem, 'versions_readable': True, 'initial_versions_readable': True})
    if not records:
        raise ValueError('Sem publicações para auditar retenção')
    return {'status': 'passed', 'minimum_days': 30, 'published_pins': 'indefinite', 'publications': records}


def retention_fixture(spark):
    """Não recebe paths: VACUUM 0 só pode atingir uma tabela sintética efêmera."""
    from delta.tables import DeltaTable
    with tempfile.TemporaryDirectory(prefix='credit-risk-retention-fixture-') as temporary:
        path = Path(temporary) / 'synthetic_delta'
        spark.createDataFrame([(1, 10)], 'case_id long, amount long').coalesce(1).write.format('delta').save(str(path))
        table = DeltaTable.forPath(spark, str(path))
        table.update(set={'amount': 'amount + 1'})
        before = spark.read.format('delta').option('versionAsOf', 0).load(str(path)).first().amount
        table.vacuum(720).collect()
        protected = spark.read.format('delta').option('versionAsOf', 0).load(str(path)).first().amount
        conf = 'spark.databricks.delta.retentionDurationCheck.enabled'
        prior = spark.conf.get(conf, None)
        try:
            spark.conf.set(conf, 'false')
            table.vacuum(0).collect()
        finally:
            if prior is None:
                spark.conf.unset(conf)
            else:
                spark.conf.set(conf, prior)
        lost = False
        try:
            spark.read.format('delta').option('versionAsOf', 0).load(str(path)).collect()
        except Exception as error:
            # Só contar a falha esperada de dados históricos removidos.
            message = str(error)
            if 'FileNotFound' not in message and 'DELTA_FILE_NOT_FOUND' not in message and 'does not exist' not in message:
                raise
            lost = True
        current = spark.read.format('delta').load(str(path)).first().amount
        if before != 10 or protected != 10 or current != 11 or not lost:
            raise AssertionError('Prova de retenção não corresponde ao oráculo 10 → 11')
        return {'status': 'passed', 'data_kind': 'synthetic_fixture_only', 'protected_by_720_hours': True,
                'forced_fixture_vacuum_loses_old_data': lost, 'current_value': current,
                'real_data_cleaned': False, 'elapsed_30_days_not_simulated': True}
