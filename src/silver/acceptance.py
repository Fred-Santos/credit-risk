"""Recibo imutável de aceite inicial local; sem ponteiro global de publicação."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.silver.initial_delta import _files


def _local(repo: Path, value: str) -> Path:
    path = (repo / value).resolve()
    if not path.is_relative_to(repo.resolve()) or not path.is_file():
        raise ValueError('Artefato ausente ou fora do repositório')
    return path


def _check_report(repo: Path, root: Path, report: dict):
    if (report.get('status') != 'passed' or report.get('scope') != 'silver_initial_operational_acceptance'
            or report.get('validation', {}).get('status') != 'passed'
            or not report['validation'].get('checks')
            or not all(c['success'] for c in report['validation']['checks'])
            or report.get('transformation_validation', {}).get('status') != 'passed'):
        raise ValueError('Aceite exige transformação e contratos aprovados')
    if (report['materialization']['root'] != root.relative_to(repo).as_posix()
            or report['selection_id'] != report['input']['selection_id']
            or report['selection_id'] != root.parent.parent.name):
        raise ValueError('Relatório e pacote Silver incompatíveis')
    manifest_path = _local(repo, str(root / '_materialization.json'))
    if report['materialization_manifest_sha256'] != sha256(manifest_path):
        raise ValueError('Manifesto técnico mudou antes do aceite')
    manifest = json.loads(manifest_path.read_text())
    if manifest != report['materialization']['manifest'] or manifest['output_checksums'] != _files(root):
        raise ValueError('Pacote Delta mudou antes do aceite')


def _write_once(path: Path, value: dict):
    """Publica um arquivo completo por hard link local, recusando substituição."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.acceptance_', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(value, indent=2) + '\n')
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_acceptance(repo: Path, root: Path, report_path: Path, report: dict) -> Path:
    """Só recebe relatório produzido após saída normal dos leitores protegidos."""
    with _ingestion_lock(root.parent, '.initial_delta.lock'):
        _check_report(repo, root, report)
        for name, digest in report['artifact_sha256'].items():
            if sha256(_local(repo, name)) != digest:
                raise RuntimeError('Código ou configuração mudou durante a execução Silver')
        receipt_path = root.parent.parent / 'acceptances' / f"{report['run_id']}.json"
        receipt = {'format_version': 1, 'status': 'passed',
                   'scope': 'silver_initial_only', 'run_id': report['run_id'],
                   'selection_id': report['selection_id'], 'materialization_id': root.name,
                   'materialization_root': root.relative_to(repo).as_posix(),
                   'materialization_manifest_sha256': report['materialization_manifest_sha256'],
                   'run_report': report_path.relative_to(repo).as_posix(),
                   'tables': {n: {k: t[k] for k in ('version', 'delta_table_id', 'rows')}
                              for n, t in report['materialization']['manifest']['tables'].items()}}
        # Relatório novo e recibo nunca substituem uma execução anterior.
        _write_once(report_path, report)
        receipt['run_report_sha256'] = sha256(report_path)
        _write_once(receipt_path, receipt)
        return receipt_path


def verify_acceptance(repo: Path, receipt_path: Path) -> dict:
    """Audita recibo, relatório e pacote; leitura tabular continua pelo leitor Delta.

    Não exige código atual igual ao histórico: o relatório fixa a implementação
    executada. Não substitui os contratos de publicação/retencão de F05.
    """
    receipt = json.loads(_local(repo, str(receipt_path)).read_text())
    if (receipt.get('format_version') != 1 or receipt.get('status') != 'passed'
            or receipt.get('scope') != 'silver_initial_only'):
        raise ValueError('Recibo Silver inválido')
    report_path = _local(repo, receipt['run_report'])
    if sha256(report_path) != receipt['run_report_sha256']:
        raise ValueError('Relatório de aceite alterado')
    report = json.loads(report_path.read_text())
    root = _local(repo, receipt['materialization_root'] + '/_materialization.json').parent
    expected_path = root.parent.parent / 'acceptances' / f"{report['run_id']}.json"
    with _ingestion_lock(root.parent, '.initial_delta.lock'):
        _check_report(repo, root, report)
        tables = {n: {k: t[k] for k in ('version', 'delta_table_id', 'rows')}
                  for n, t in report['materialization']['manifest']['tables'].items()}
        if (receipt_path.resolve() != expected_path.resolve()
                or receipt['run_id'] != report['run_id'] or receipt['selection_id'] != report['selection_id']
                or receipt['materialization_id'] != root.name or receipt['tables'] != tables
                or receipt['materialization_manifest_sha256'] != report['materialization_manifest_sha256']):
            raise ValueError('Vínculo do recibo Silver divergente')
    return receipt
