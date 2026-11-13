"""Vínculo explícito entre snapshot de entrada, namespace Bronze e relatórios."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from src.pipelines.build_sample import verify_committed
from src.pipelines.download_home_credit import sha256
from src.utils.run_context import RunContext


@dataclass(frozen=True)
class BronzeInput:
    ctx: RunContext
    descriptor: dict
    expected_counts: dict[str, int] | None


def _scoped_context(ctx: RunContext, input_dir: Path, namespace: Path,
                    selection_id: str | None) -> RunContext:
    reports = ctx.repo_root / 'artifacts' / 'bronze' / namespace
    return replace(ctx, input_dir=input_dir, selection_id=selection_id,
                   bronze_dir=ctx.bronze_dir / namespace, docs_root=reports,
                   data_dictionary_dir=reports / 'dictionary', data_quality_dir=reports / 'quality',
                   lineage_dir=reports / 'lineage', observability_dir=reports / 'observability')


def bind_sample(ctx: RunContext, selection_id: str) -> BronzeInput:
    if not re.fullmatch(r'[0-9a-f]{24}', selection_id):
        raise ValueError('selection_id deve ter 24 caracteres hexadecimais minúsculos')
    sample = (ctx.sample_dir / selection_id).resolve()
    if not sample.is_relative_to(ctx.sample_dir.resolve()) or not sample.is_dir():
        raise ValueError('Recorte ausente ou fora do diretório de seleções')
    path = sample / '_selection.json'
    if not path.is_file():
        raise ValueError('Recorte não publicado: _selection.json ausente')
    manifest = json.loads(path.read_text())
    identity = manifest['identity']
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if (digest != manifest['identity_sha256'] or digest[:24] != selection_id
            or manifest['selection_id'] != selection_id):
        raise ValueError('Identidade do recorte não corresponde ao manifesto/diretório')
    contract = ctx.repo_root / 'configs/contracts/home_credit_v1.yaml'
    if sha256(contract) != identity['contract_sha256']:
        raise ValueError('Contrato atual difere do contrato do recorte; selecione a versão compatível')
    for field in ('source_validation', 'sample_validation'):
        validation = manifest[field]
        if (validation['status'] != 'passed' or not validation.get('checks')
                or not all(check['success'] for check in validation['checks'])):
            raise ValueError('Recorte não aprovado pelos contratos')
    verify_committed(sample, identity)
    counts = manifest['counts']
    if (not counts or any(type(value) is not int or value < 0 for value in counts.values())
            or counts.get('train_base') != manifest['case_count'] or manifest['case_count'] <= 0):
        raise ValueError('Contagens inválidas no manifesto do recorte')
    for name in counts:
        if not re.fullmatch(r'train_[a-z0-9_]+', name) or not (sample / 'parquet_files/train' / name).is_dir():
            raise ValueError(f'Dataset do recorte ausente ou inválido: {name}')
    descriptor = {'kind': 'sample', 'selection_id': selection_id,
                  'input_dir': sample.relative_to(ctx.repo_root).as_posix(),
                  'sample_manifest_sha256': sha256(path), 'sample_identity_sha256': digest,
                  'contract_sha256': identity['contract_sha256']}
    scoped = _scoped_context(ctx, sample, Path('samples') / selection_id, selection_id)
    return BronzeInput(scoped, descriptor, counts)


def bind_raw(ctx: RunContext) -> BronzeInput:
    # Caminho separado evita misturar o modo RAW com o contêiner de seleções.
    scoped = _scoped_context(ctx, ctx.raw_dir, Path('raw'), None)
    return BronzeInput(scoped, {'kind': 'raw', 'input_dir': ctx.raw_dir.relative_to(ctx.repo_root).as_posix()}, None)


def verify_input(bound: BronzeInput):
    if bound.descriptor['kind'] != 'sample':
        return
    root = bound.ctx.ingestion_dir
    manifest_path = root / '_selection.json'
    if sha256(manifest_path) != bound.descriptor['sample_manifest_sha256']:
        raise RuntimeError('Manifesto do recorte mudou durante a execução')
    manifest = json.loads(manifest_path.read_text())
    verify_committed(root, manifest['identity'])
    contract = bound.ctx.repo_root / 'configs/contracts/home_credit_v1.yaml'
    if sha256(contract) != bound.descriptor['contract_sha256']:
        raise RuntimeError('Contrato do recorte mudou durante a execução')
