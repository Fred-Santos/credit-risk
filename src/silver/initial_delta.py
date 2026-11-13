"""Materialização Delta inicial em pacote imutável no filesystem local.

O manifesto técnico não é o aceite Silver completo, que depende de F03.5/F03.6.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.quality.contracts import check_schema
from src.quality.reconcile_bronze import compare_rows

TABLES = {'train_base': 'credit_cases', 'train_static_0': 'credit_static',
          'train_applprev_1': 'previous_applications'}
STATUS = 'materialized_pending_silver_acceptance'


def identity_digest(identity: dict) -> str:
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _files(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and (p.suffix == '.parquet'
                                or ('_delta_log' in p.parts and not p.name.startswith('.')))}


def _verify(root: Path, spark, expected_identity: dict | None = None):
    from delta.tables import DeltaTable

    manifest = json.loads((root / '_materialization.json').read_text())
    digest = identity_digest(manifest['identity'])
    if (manifest.get('format_version') != 1 or manifest.get('status') != STATUS
            or digest != manifest['identity_sha256'] or root.name != digest[:24]
            or (expected_identity is not None and manifest['identity'] != expected_identity)
            or manifest.get('table_mapping') != TABLES or set(manifest['tables']) != set(TABLES.values())):
        raise ValueError('Manifesto ou identidade da materialização inválido')
    if not manifest.get('output_checksums') or manifest['output_checksums'] != _files(root):
        raise ValueError('Arquivos/log Delta ausentes, extras ou alterados')
    folders = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')}
    if folders != set(TABLES.values()):
        raise ValueError('Conjunto de tabelas Delta inesperado')
    frames = {}
    for source, name in TABLES.items():
        entry = manifest['tables'][name]
        path = root / name
        if (not path.resolve().is_relative_to(root.resolve()) or entry['path'] != name
                or entry['source_table'] != source or type(entry['version']) is not int
                or entry['version'] != 0 or not DeltaTable.isDeltaTable(spark, str(path))):
            raise ValueError(f'Tabela não corresponde ao snapshot Delta inicial: {name}')
        delta = DeltaTable.forPath(spark, str(path))
        detail = delta.detail().select('id', 'format').first()
        latest = delta.history(1).select('version').first()[0]
        if detail['id'] != entry['delta_table_id'] or detail['format'] != 'delta' or latest != entry['version']:
            raise ValueError(f'Identidade/versão Delta alterada: {name}')
        frame = spark.read.format('delta').option('versionAsOf', entry['version']).load(str(path))
        check_schema(frame, {'schema': entry['schema']})
        proof = entry['readback_proof']
        if (frame.count() != entry['rows'] or proof != {'success': True, 'missing_rows': 0, 'extra_rows': 0}):
            raise ValueError(f'Conteúdo Delta sem reconciliação: {name}')
        frames[name] = frame
    return frames, manifest


def materialize_initial(parent: Path, spark, *, identity: dict, frames: dict,
                        keys: dict, run_id: str, existing: str = 'reuse') -> dict:
    from delta.tables import DeltaTable

    if existing not in {'reuse', 'error'}:
        raise ValueError('Comportamento para pacote existente inválido')
    if set(frames) != set(TABLES) or set(keys) != set(TABLES):
        raise ValueError('Materialização inicial exige as três tabelas contratadas')
    digest = identity_digest(identity)
    root = parent / digest[:24]
    parent.mkdir(parents=True, exist_ok=True)
    with _ingestion_lock(parent, '.initial_delta.lock'):
        if root.exists():
            if existing == 'error':
                raise FileExistsError(f'Pacote Silver já existe: {root.name}')
            stored, manifest = _verify(root, spark, identity)
            for source, name in TABLES.items():
                check_schema(stored[name], {'schema': dict(frames[source].dtypes)})
                if not compare_rows(frames[source], stored[name], frames[source].columns)['success']:
                    raise ValueError(f'Retry com conteúdo diferente: {name}')
            return {'root': str(root), 'reused': True, 'manifest': manifest}
        stage = Path(tempfile.mkdtemp(prefix='.initial_stage_', dir=parent))
        try:
            entries = {}
            for source, name in TABLES.items():
                frame, path = frames[source], stage / name
                frame.write.format('delta').mode('errorifexists').save(str(path))
                delta = DeltaTable.forPath(spark, str(path))
                latest = delta.history(1).select('version', 'operation').first()
                if latest['version'] != 0 or latest['operation'] != 'WRITE':
                    raise ValueError(f'Criação inicial não produziu versão zero: {name}')
                stored = spark.read.format('delta').option('versionAsOf', 0).load(str(path))
                check_schema(stored, {'schema': dict(frame.dtypes)})
                proof = compare_rows(frame, stored, frame.columns)
                if not proof['success']:
                    raise ValueError(f'Leitura Delta diverge da transformação: {name}')
                entries[name] = {
                    'source_table': source, 'path': name, 'version': 0,
                    'delta_table_id': delta.detail().select('id').first()[0],
                    'rows': stored.count(), 'schema': dict(stored.dtypes), 'key': keys[source],
                    'operation': latest['operation'], 'readback_proof': proof,
                }
            manifest = {'format_version': 1, 'status': STATUS, 'identity': identity,
                        'identity_sha256': digest, 'created_by_run_id': run_id,
                        'table_mapping': TABLES, 'tables': entries,
                        'output_checksums': _files(stage)}
            (stage / '_materialization.json').write_text(json.dumps(manifest, indent=2) + '\n')
            # Logs AddFile usam paths relativos; o pacote completo move no mesmo filesystem.
            stage.rename(root)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return {'root': str(root), 'reused': False, 'manifest': manifest}


@contextmanager
def open_initial_tables(root: Path, spark):
    """Leitura técnica com Delta e versões fixadas; não autoriza consumo Gold."""
    with _ingestion_lock(root.parent, '.initial_delta.lock'):
        frames, manifest = _verify(root, spark)
        original_hash = sha256(root / '_materialization.json')
        yield frames, manifest
        _verify(root, spark)
        if original_hash != sha256(root / '_materialization.json'):
            raise RuntimeError('Manifesto mudou durante leitura Delta')
