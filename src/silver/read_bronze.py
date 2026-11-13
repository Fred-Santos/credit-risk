"""Leitor local de snapshot: consumir DataFrames dentro do contexto protegido."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import reduce
import hashlib
import json
from pathlib import Path

from src.bronze.build_bronze import _discover_inputs, _ingestion_lock, _output_checksums, _source_record
from src.bronze.inputs import BronzeInput, verify_input
from src.pipelines.download_home_credit import sha256
from src.quality.bronze_contract import METADATA
from src.quality.contracts import check_schema, load_contract
from src.quality.reconcile_bronze import audit_lineage


def _local(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Artefato ausente ou fora do namespace esperado')
    return path


def _index(root: Path) -> dict:
    files = [p for p in root.rglob('*') if p.is_file()
             and (p.suffix == '.parquet' or p.name in {'_input.json', '_ingestion.json'})]
    return {p.relative_to(root).as_posix(): sha256(_local(root, p.relative_to(root).as_posix())) for p in sorted(files)}


def verify_approval(bound: BronzeInput) -> dict:
    ctx = bound.ctx
    if bound.descriptor['kind'] != 'sample':
        raise ValueError('Leitor Silver inicial exige um recorte aprovado explícito')
    verify_input(bound)
    root = ctx.bronze_dir
    gate_path = _local(root, '_READY.json')
    gate = json.loads(gate_path.read_text())
    if (type(gate.get('format_version')) is not int or gate['format_version'] != 1
            or gate.get('status') != 'passed' or gate.get('input') != bound.descriptor
            or gate.get('counts') != bound.expected_counts):
        raise ValueError('Gate incompatível com a seleção ou sem aprovação')
    if json.loads(_local(root, '_input.json').read_text()) != bound.descriptor:
        raise ValueError('Vínculo de entrada Bronze divergente')
    if not gate.get('output_checksums') or gate['output_checksums'] != _index(root):
        raise ValueError('Arquivos Bronze ausentes, extras ou alterados')
    reports = ctx.docs_root
    run_path = _local(reports, str(_local(ctx.repo_root, gate['run_report'])))
    run = json.loads(run_path.read_text())
    if (run.get('status') != 'passed' or run.get('run_id') != gate['verified_by_run_id']
            or run.get('input') != bound.descriptor or run.get('counts') != gate['counts']):
        raise ValueError('Relatório de execução não corresponde ao gate')
    contract_hash = sha256(ctx.repo_root / 'configs/contracts/home_credit_v1.yaml')
    config_hash = sha256(ctx.repo_root / 'configs/quality_rules_bronze.yaml')
    if gate['quality_config_sha256'] != config_hash or run['quality_config_sha256'] != config_hash:
        raise ValueError('Qualidade configurada mudou; revalidar Bronze')
    quality_path = _local(reports, run['quality']['json'])
    quality = json.loads(quality_path.read_text())
    if (sha256(quality_path) != gate['quality_report_sha256']
            or quality.get('run_id') != gate['verified_by_run_id']
            or quality.get('snapshot_contract_sha256') != contract_hash
            or quality.get('failed_checks') != 0 or not quality.get('results')
            or any(not c['success'] and c['severity'] == 'fail' for c in quality['results'])):
        raise ValueError('Qualidade não aprovada ou relatório alterado')
    rec_path = _local(reports, run['reconciliation']['json'])
    rec = json.loads(rec_path.read_text())
    if (sha256(rec_path) != gate['reconciliation_report_sha256'] or rec.get('status') != 'passed'
            or rec.get('run_id') != gate['verified_by_run_id'] or rec.get('selection_id') != ctx.selection_id
            or rec.get('contract_sha256') != contract_hash or not rec.get('checks') or not all(rec['checks'])):
        raise ValueError('Reconciliação não aprovada ou relatório alterado')
    files = {str((root / name).relative_to(ctx.repo_root)): digest
             for name, digest in gate['output_checksums'].items() if name != '_input.json'}
    lineage_path = _local(reports, run['lineage']['json'])
    if not audit_lineage(replace(ctx, run_id=gate['verified_by_run_id']), lineage_path, files)['success']:
        raise ValueError('Lineage incompatível com a publicação')
    return {'gate': gate, 'gate_sha256': sha256(gate_path), 'run_report_sha256': sha256(run_path),
            'contract_sha256': contract_hash, 'quality_config_sha256': config_hash,
            'lineage_sha256': sha256(lineage_path)}


@dataclass
class LoadedBronze:
    frames: dict
    receipt: dict


@contextmanager
def open_bronze_snapshot(bound: BronzeInput, spark):
    """Lock mantido durante leitura, validação e ações Spark do consumidor.

    Não devolver planos preguiçosos para execução fora do with. Nenhum cast,
    join de enriquecimento ou transformação de payload ocorre neste leitor.
    """
    from pyspark.sql import functions as F
    from functools import reduce as combine

    ctx = bound.ctx
    if not ctx.bronze_dir.is_dir():
        raise ValueError('Namespace Bronze ausente')
    with _ingestion_lock(ctx.bronze_dir, '.pipeline.lock'):
        approval = verify_approval(bound)
        contract = load_contract(ctx.repo_root / 'configs/contracts/home_credit_v1.yaml')
        inputs = dict(_discover_inputs(ctx.ingestion_dir / 'parquet_files/train'))
        expected_tables = set(contract['tables'])
        observed_tables = {p.name for p in ctx.bronze_dir.iterdir() if p.is_dir() and not p.name.startswith(('.', '_'))}
        if set(inputs) != expected_tables or observed_tables != expected_tables:
            raise ValueError('Conjunto de tabelas difere do contrato')
        frames, details = {}, {}
        for name, spec in contract['tables'].items():
            table_root = ctx.bronze_dir / name
            ordered = list(spec['schema']) + list(METADATA)
            expected_schema = {**spec['schema'], **METADATA}
            shards, batches = [], []
            for filename in inputs[name]:
                source = _source_record(Path(filename), ctx.ingestion_dir)
                batch = hashlib.sha256(source['path'].encode()).hexdigest()
                batch_root = table_root / f'ingest_batch={batch}'
                manifest = json.loads(_local(batch_root, '_ingestion.json').read_text())
                outputs = _output_checksums(batch_root)
                if manifest.get('format_version') != 2 or manifest.get('source') != source or not outputs or manifest.get('output_files') != outputs:
                    raise ValueError(f'Manifesto de ingestão inválido: {name}')
                for relative in sorted(outputs):
                    file = _local(batch_root, relative)
                    frame = spark.read.option('basePath', str(table_root)).parquet(str(file))
                    check_schema(frame, {'schema': expected_schema})
                    invalid = (~F.col('_run_id').eqNullSafe(F.lit(manifest['run_id']))
                               | ~F.col('ingest_batch').eqNullSafe(F.lit(batch)))
                    if frame.filter(invalid).limit(1).count():
                        raise ValueError(f'Proveniência de shard inválida: {name}')
                    shards.append(frame.select(*ordered))
                batches.append(batch_root.name)
            observed_batches = {p.name for p in table_root.iterdir() if p.is_dir() and not p.name.startswith(('.', '_'))}
            if observed_batches != set(batches) or not shards:
                raise ValueError(f'Batches ausentes ou extras: {name}')
            frame = reduce(lambda a, b: a.unionByName(b), shards)
            required = spec['required_non_null'] + list(METADATA)
            nulls = combine(lambda a, b: a | b, [F.col(c).isNull() for c in required])
            count = frame.count()
            if (count != bound.expected_counts[name] or count < spec['minimum_rows']
                    or frame.filter(nulls).limit(1).count()
                    or frame.groupBy(*spec['key']).count().filter('count > 1').limit(1).count()):
                raise ValueError(f'Contagem/chave/nulos obrigatórios inválidos após união: {name}')
            frames[name] = frame
            details[name] = {'rows': count, 'columns': len(frame.columns), 'key': spec['key'],
                             'shards': len(shards), 'batches': batches}
        receipt = {'selection_id': ctx.selection_id, 'bronze_run_id': approval['gate']['verified_by_run_id'],
                   'gate_sha256': approval['gate_sha256'], 'contract_sha256': approval['contract_sha256'],
                   'run_report_sha256': approval['run_report_sha256'],
                   'lineage_sha256': approval['lineage_sha256'],
                   'quality_report_sha256': approval['gate']['quality_report_sha256'],
                   'reconciliation_report_sha256': approval['gate']['reconciliation_report_sha256'],
                   'tables': details, 'status': 'validated_read_only'}
        yield LoadedBronze(frames, receipt)
        # Detecta alterações externas ao protocolo; leitores devem manter suas ações no with.
        if verify_approval(bound) != approval:
            raise RuntimeError('Publicação Bronze mudou durante o consumo')
