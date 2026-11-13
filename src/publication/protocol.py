"""Protocolo POSIX local: commits privados, manifesto imutável e CURRENT atômico.

Um escritor por registry. Consumidores mantêm o contexto aberto durante ações
Spark. Não fornece transação distribuída nem commit em armazenamento de objetos.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import uuid

import yaml

from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.quality.contracts import check_schema
from src.quality.event_contracts import digest
from src.silver.acceptance import _write_once
from src.silver.initial_delta import _files
from src.silver.incremental import _commit_metadata, _restore_conf


class NoPublicationError(FileNotFoundError):
    pass


class InjectedFailure(RuntimeError):
    pass


def fail_at(target: str):
    def hook(stage):
        if stage == target:
            raise InjectedFailure(f'Falha simulada: {stage}')
    return hook


def load_publication_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text())
    expected = {'version': 1, 'storage': 'local_filesystem',
        'writer': 'single_exclusive_nonblocking_lock',
        'visibility': 'immutable_manifest_then_atomic_current_pointer',
        'recovery': 'inspect_tagged_delta_commits_and_resume_same_intent',
        'retention_days': 30, 'published_versions': 'pin_all_indefinitely_until_explicit_retirement',
        'real_vacuum': 'forbidden',
        'destructive_retention_demo': 'internally_created_temporary_fixture_only'}
    if policy != expected or type(policy.get('version')) is not int or type(policy.get('retention_days')) is not int:
        raise ValueError('Política de publicação/retenção não suportada')
    return policy


def local(repo: Path, relative: str, *, exists=True) -> Path:
    path = (repo / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(repo.resolve()) or path == repo.resolve():
        raise ValueError('Artefato fora do repositório')
    if exists and not path.exists():
        raise ValueError(f'Artefato ausente: {relative}')
    return path


def atomic_json(path: Path, value: dict):
    """Arquivo completo + replace no mesmo filesystem; fsync de arquivo/diretório."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(value, indent=2) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def archive_provenance(repo: Path, registry: Path, fingerprints: dict) -> dict:
    result = {}
    for name, expected in fingerprints.items():
        source = local(repo, name)
        if sha256(source) != expected:
            raise ValueError('Proveniência mudou durante preparação')
        destination = registry / 'blobs' / expected
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256(destination) != expected:
                raise ValueError('Blob de proveniência alterado')
        else:
            # O registry está sob lock; blobs têm identidade de conteúdo.
            temporary = destination.with_name('.' + expected + '.tmp')
            temporary.write_bytes(source.read_bytes())
            os.link(temporary, destination)
            temporary.unlink()
        result[name] = {'path': destination.relative_to(repo).as_posix(), 'sha256': expected}
    return result


def _id(value: str):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{24}', value):
        raise ValueError('publication_id deve ter 24 caracteres hexadecimais')


def _table_frame(repo: Path, spark, entry: dict):
    from delta.tables import DeltaTable
    path = local(repo, entry['path'])
    if entry['files'] != _files(path) or not entry['files']:
        raise ValueError('Arquivos/logs de publicação ausentes, extras ou alterados')
    table = DeltaTable.forPath(spark, str(path))
    if (table.detail().select('id').first()[0] != entry['delta_table_id']
            or int(table.history(1).select('version').first()[0]) != entry['version']):
        raise ValueError('UUID/versão de tabela publicada mudou')
    frame = spark.read.format('delta').option('versionAsOf', entry['version']).load(str(path))
    check_schema(frame, {'schema': entry['schema']})
    if frame.count() != entry['rows']:
        raise ValueError('Contagem publicada divergente')
    return frame


def verify_manifest(repo: Path, registry: Path, publication_id: str, spark, *, seen=None):
    _id(publication_id)
    path = registry / 'manifests' / (publication_id + '.json')
    manifest = json.loads(path.read_text())
    if (manifest.get('format_version') != 1 or manifest.get('status') != 'passed'
            or manifest.get('publication_id') != publication_id
            or digest(manifest['identity'])[:24] != publication_id or not manifest.get('tables')
            or any(v.get('status') != 'passed' for v in manifest.get('validations', {}).values())
            or not manifest.get('validations')):
        raise ValueError('Manifesto de publicação inválido')
    visited = set() if seen is None else set(seen)
    if str(path.resolve()) in visited:
        raise ValueError('Referência cíclica de publicação')
    visited.add(str(path.resolve()))
    for source in manifest.get('references', []):
        linked = local(repo, source['manifest'])
        if sha256(linked) != source['sha256']:
            raise ValueError('Manifesto de entrada alterado')
        linked_id = linked.stem
        verify_manifest(repo, linked.parent.parent, linked_id, spark, seen=visited)
    for record in manifest['provenance'].values():
        if sha256(local(repo, record['path'])) != record['sha256']:
            raise ValueError('Proveniência arquivada alterada')
    frames = {name: _table_frame(repo, spark, entry) for name, entry in manifest['tables'].items()}
    return manifest, frames


def current_id(registry: Path) -> str:
    path = registry / '_CURRENT.json'
    if not path.is_file():
        raise NoPublicationError('Ainda não existe publicação aprovada neste registry')
    pointer = json.loads(path.read_text())
    _id(pointer['publication_id'])
    manifest_path = registry / 'manifests' / (pointer['publication_id'] + '.json')
    if sha256(manifest_path) != pointer['manifest_sha256']:
        raise ValueError('Ponteiro CURRENT não corresponde ao manifesto')
    return pointer['publication_id']


def _activate(repo: Path, registry: Path, manifest: dict, run_id: str, *, reason: str):
    publication_id = manifest['publication_id']
    path = registry / 'manifests' / (publication_id + '.json')
    if (registry / '_CURRENT.json').exists() and current_id(registry) == publication_id:
        return {'reused': True, 'publication_id': publication_id}
    value = {'format_version': 1, 'publication_id': publication_id, 'manifest_sha256': sha256(path),
             'activated_by_run_id': run_id, 'reason': reason,
             'activated_at_utc': datetime.now(timezone.utc).isoformat()}
    activation = registry / 'activations' / (run_id + '_' + uuid.uuid4().hex[:8] + '.json')
    _write_once(activation, value)
    atomic_json(registry / '_CURRENT.json', value)
    return {**value, 'reused': False}


@contextmanager
def open_publication(repo: Path, registry: Path, spark, publication_id: str | None = None):
    registry.mkdir(parents=True, exist_ok=True)
    with _ingestion_lock(registry, '.publication.lock'):
        chosen = current_id(registry) if publication_id is None else publication_id
        manifest, frames = verify_manifest(repo, registry, chosen, spark)
        original = sha256(registry / 'manifests' / (chosen + '.json'))
        yield manifest, frames
        if sha256(registry / 'manifests' / (chosen + '.json')) != original:
            raise RuntimeError('Manifesto mudou durante consumo')
        # Conferir arquivos novamente, sem repetir as ações de profiling.
        for entry in manifest['tables'].values():
            if _files(local(repo, entry['path'])) != entry['files']:
                raise RuntimeError('Tabela publicada mudou durante consumo')


def activate_publication(repo: Path, registry: Path, spark, publication_id: str, run_id: str):
    with _ingestion_lock(registry, '.publication.lock'):
        manifest, _ = verify_manifest(repo, registry, publication_id, spark)
        return _activate(repo, registry, manifest, run_id, reason='explicit_rollback_or_restore')


class PublicationTransaction:
    """Usar dentro de registry lock; tentativas deixam commits privados retomáveis."""

    def __init__(self, ctx, registry: Path, spark, identity: dict, fingerprints: dict, *, hook=None):
        self.ctx, self.repo, self.registry, self.spark = ctx, ctx.repo_root, registry, spark
        self.identity = identity
        self.id = digest(identity)[:24]
        self.hook = hook or (lambda stage: None)
        self.path = registry / 'intents' / (self.id + '.json')
        self.provenance = archive_provenance(self.repo, registry, fingerprints)
        if self.path.exists():
            self.intent = json.loads(self.path.read_text())
            if self.intent['identity'] != identity:
                raise ValueError('Intento existente com outra identidade')
        else:
            self.intent = {'publication_id': self.id, 'identity': identity,
                           'token': uuid.uuid4().hex, 'first_run_id': ctx.run_id}
            _write_once(self.path, self.intent)
        self.entries, self.validations, self.details = {}, {}, {}

    def table_path(self, layer: str, name: str):
        if layer not in {'silver', 'gold'} or not re.fullmatch(r'[a-z][a-z0-9_]+', name):
            raise ValueError('Camada/nome de tabela inválido')
        base = self.ctx.silver_dir if layer == 'silver' else self.ctx.gold_dir
        path = base / 'samples' / self.identity['selection_id'] / 'published' / self.id / name
        if not path.resolve().is_relative_to(base.resolve()):
            raise ValueError('Tabela fora do namespace da camada')
        return path

    def metadata(self, key: str, stage: str):
        return {'scope': 'managed_publication_v1', 'publication_id': self.id,
                'token': self.intent['token'], 'table': key, 'stage': stage}

    @contextmanager
    def commit(self, key: str, stage: str):
        self.hook('before_commit:' + key + ':' + stage)
        name, prior = _commit_metadata(self.spark, self.metadata(key, stage))
        try:
            yield
        finally:
            _restore_conf(self.spark, name, prior)
        self.hook('after_commit:' + key + ':' + stage)

    def verify_owned(self, path: Path, key: str):
        from delta.tables import DeltaTable
        delta = DeltaTable.forPath(self.spark, str(path))
        history = delta.history().select('version', 'userMetadata').collect()
        for row in history:
            meta = json.loads(row.userMetadata or '{}')
            if any(meta.get(n) != v for n, v in self.metadata(key, meta.get('stage', '')).items()):
                raise ValueError('Commit privado não pertence a este intento')
        return delta

    def create_table(self, layer: str, name: str, initial):
        from delta.tables import DeltaTable
        path, key = self.table_path(layer, name), layer + '.' + name
        owner = self.registry / 'owners' / self.id / (key + '.json')
        ownership = {'token': self.intent['token'], 'path': path.relative_to(self.repo).as_posix()}
        if path.exists() and not owner.is_file():
            raise ValueError('Diretório existente sem vínculo; não será sobrescrito')
        if owner.exists() and json.loads(owner.read_text()) != ownership:
            raise ValueError('Proprietário do diretório privado incompatível')
        if not owner.exists():
            _write_once(owner, ownership)
        if path.exists():
            if DeltaTable.isDeltaTable(self.spark, str(path)):
                return self.verify_owned(path, key)
            if any(re.fullmatch(r'\d{20}\.json', p.name) for p in (path / '_delta_log').glob('*.json')):
                raise ValueError('Log Delta corrompido; não remover commits existentes')
            # Somente área privada pertencente ao intento, sem commit existente.
            shutil.rmtree(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.commit(key, 'create'):
            (initial.write.format('delta').mode('errorifexists')
             .option('delta.logRetentionDuration', 'interval 30 days')
             .option('delta.deletedFileRetentionDuration', 'interval 30 days').save(str(path)))
        return DeltaTable.forPath(self.spark, str(path))

    def record_table(self, layer: str, name: str, schema: dict, key: list):
        path, table_key = self.table_path(layer, name), layer + '.' + name
        table = self.verify_owned(path, table_key)
        detail = table.detail().select('id', 'properties').first()
        if (detail.properties.get('delta.logRetentionDuration') != 'interval 30 days'
                or detail.properties.get('delta.deletedFileRetentionDuration') != 'interval 30 days'):
            raise ValueError('Retenção Delta não corresponde ao contrato')
        version = int(table.history(1).select('version').first()[0])
        frame = self.spark.read.format('delta').option('versionAsOf', version).load(str(path))
        check_schema(frame, {'schema': schema})
        self.entries[table_key] = {'path': path.relative_to(self.repo).as_posix(),
            'delta_table_id': detail.id, 'version': version, 'schema': schema, 'rows': frame.count(),
            'key': key, 'files': _files(path), 'storage_publication_id': self.id}
        return frame

    def publish(self, *, references=None):
        if not self.entries or not self.validations or any(v.get('status') != 'passed' for v in self.validations.values()):
            raise ValueError('Publicação exige todas as validações aprovadas')
        manifest = {'format_version': 1, 'status': 'passed', 'publication_id': self.id,
            'identity': self.identity, 'created_by_run_id': self.ctx.run_id,
            'tables': self.entries, 'validations': self.validations, 'details': self.details,
            'provenance': self.provenance, 'references': references or [],
            'retention': {'minimum_days': 30, 'all_publications_pinned': True, 'real_vacuum': 'forbidden'}}
        self.hook('before_manifest')
        _write_once(self.registry / 'manifests' / (self.id + '.json'), manifest)
        self.hook('before_pointer')
        activation = _activate(self.repo, self.registry, manifest, self.ctx.run_id, reason='validated_publication')
        self.hook('after_pointer')
        return manifest, activation


def publish_snapshot(ctx, registry: Path, spark, identity: dict, fingerprints: dict, builder, *, hook=None):
    """Serializa criação/retomada/publicação; builder preenche tabelas e validações."""
    registry.mkdir(parents=True, exist_ok=True)
    publication_id = digest(identity)[:24]
    started = datetime.now(timezone.utc).isoformat()
    report_path = registry / 'runs' / (ctx.run_id + '_' + publication_id + '.json')
    if report_path.exists():
        raise FileExistsError('Tentativa já registrada; use novo RunContext para retry')
    report = {'run_id': ctx.run_id, 'publication_id': publication_id,
              'status': 'running', 'started_at_utc': started, 'identity': identity}
    try:
        with _ingestion_lock(registry, '.publication.lock'):
            path = registry / 'manifests' / (publication_id + '.json')
            if path.exists():
                manifest, _ = verify_manifest(ctx.repo_root, registry, publication_id, spark)
                if manifest['identity'] != identity:
                    raise ValueError('Manifesto com identidade incompatível')
                activation = _activate(ctx.repo_root, registry, manifest, ctx.run_id, reason='verified_retry')
                report['reused'] = True
            else:
                transaction = PublicationTransaction(ctx, registry, spark, identity, fingerprints, hook=hook)
                builder(transaction)
                # Não aceitar deriva de implementação enquanto Spark executava.
                for name, expected in fingerprints.items():
                    if sha256(local(ctx.repo_root, name)) != expected:
                        raise RuntimeError('Código/configuração mudou durante publicação')
                manifest, activation = transaction.publish(references=transaction.details.pop('references', []))
                report['reused'] = False
            report.update(status='passed', manifest_sha256=sha256(path), activation=activation,
                          finished_at_utc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error),
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(report_path, report)
        raise
    atomic_json(report_path, report)
    return manifest, report
