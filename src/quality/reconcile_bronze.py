"""Reconciliação exata de multiconjuntos e proveniência do snapshot local."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.bronze.build_bronze import _discover_inputs, _output_checksums, _source_record
from src.pipelines.download_home_credit import sha256
from src.quality.contracts import load_contract, read_source_frames, source_fingerprints


def compare_rows(expected, actual, columns: list[str]) -> dict:
    """exceptAll é posicional: projetar explicitamente a mesma ordem e tipos."""
    left, right = expected.select(*columns), actual.select(*columns)
    if dict(left.dtypes) != dict(right.dtypes):
        raise ValueError('Tipos incompatíveis na reconciliação; casts automáticos proibidos')
    missing = left.exceptAll(right).count()
    extra = right.exceptAll(left).count()
    return {'success': missing == extra == 0, 'missing_rows': missing, 'extra_rows': extra}


def audit_lineage(ctx, path: Path, expected_files: dict) -> dict:
    event = json.loads(path.read_text())
    valid = (event['run']['runId'] == ctx.run_id and event['eventType'] == 'COMPLETE'
             and event['inputs'] == [{'namespace': 'file', 'name': (ctx.ingestion_dir / 'parquet_files/train').relative_to(ctx.repo_root).as_posix()}]
             and event['outputs'] == [{'namespace': 'file', 'name': ctx.bronze_dir.relative_to(ctx.repo_root).as_posix()}])
    if ctx.selection_id:
        facet = event['facets'].get('selection', {})
        manifest = ctx.ingestion_dir / '_selection.json'
        valid = valid and facet == {
            'selection_id': ctx.selection_id, 'manifest': manifest.relative_to(ctx.repo_root).as_posix(),
            'manifest_sha256': sha256(manifest),
            'original_raw_dir': ctx.raw_dir.relative_to(ctx.repo_root).as_posix()}
    entries = event['artifacts']['bronzeFiles']['files']
    indexed = {entry['path']: entry.get('sha256') for entry in entries}
    valid = valid and len(indexed) == len(entries) and all(indexed.get(name) == value for name, value in expected_files.items())
    return {'success': bool(valid), 'files_audited': len(expected_files)}


def reconcile_bronze(ctx, spark, *, lineage_path: Path) -> dict:
    from pyspark.sql import functions as F

    report = {'run_id': ctx.run_id, 'selection_id': ctx.selection_id, 'status': 'running',
              'comparison': 'spark_exceptAll_both_directions_no_cast', 'tables': {},
              'accepted_rows': 0, 'rejected_rows': 0, 'checks': []}
    path = ctx.data_quality_dir / 'reconciliation' / f'{ctx.run_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        contract_path = ctx.repo_root / 'configs/contracts/home_credit_v1.yaml'
        contract_hash = sha256(contract_path)
        contract = load_contract(contract_path)
        report['contract_sha256'] = contract_hash
        inputs = dict(_discover_inputs(ctx.ingestion_dir / 'parquet_files/train'))
        if set(inputs) != set(contract['tables']):
            raise ValueError('Tabelas de entrada fora do contrato de reconciliação')
        # Conferir também o elo RAW -> coorte -> Bronze, sem alterar a coorte.
        raw_frames = None
        source_fingerprints(ctx.raw_dir, contract)
        if ctx.selection_id:
            raw_frames = read_source_frames(spark, ctx.raw_dir, contract)
        files_index = {}
        for name, filenames in inputs.items():
            spec = contract['tables'][name]
            columns = list(spec['schema'])
            destination = ctx.bronze_dir / name
            actual = spark.read.parquet(str(destination))
            expected = spark.read.parquet(*filenames).withColumn('_source_file', F.input_file_name())
            comparison = compare_rows(expected, actual, columns)
            provenance = compare_rows(expected, actual, columns + ['_source_file'])
            row_count = expected.count()
            item = {'input_rows': row_count, 'bronze_rows': actual.count(),
                    'business_values': comparison, 'source_file_values': provenance,
                    'files': [], 'rejected_rows': 0}
            report['tables'][name] = item
            checks = [comparison['success'], provenance['success']]
            expected_batches = set()
            for filename in filenames:
                source = _source_record(Path(filename), ctx.ingestion_dir)
                batch = hashlib.sha256(source['path'].encode()).hexdigest()
                expected_batches.add(f'ingest_batch={batch}')
                batch_root = destination / f'ingest_batch={batch}'
                manifest_path = batch_root / '_ingestion.json'
                manifest = json.loads(manifest_path.read_text())
                outputs = _output_checksums(batch_root)
                valid = (manifest['format_version'] == 2 and manifest['source'] == source
                         and bool(outputs) and manifest['output_files'] == outputs)
                rows = actual.filter(F.col('ingest_batch') == batch)
                source_rows = spark.read.parquet(filename).withColumn('_source_file', F.input_file_name())
                batch_values = compare_rows(source_rows, rows, columns + ['_source_file'])
                metadata_ok = rows.filter(~F.col('_run_id').eqNullSafe(F.lit(manifest['run_id']))).limit(1).count() == 0
                checks.extend([valid, metadata_ok, batch_values['success']])
                files_index[manifest_path.relative_to(ctx.repo_root).as_posix()] = sha256(manifest_path)
                for relative, digest in outputs.items():
                    files_index[(batch_root / relative).relative_to(ctx.repo_root).as_posix()] = digest
                item['files'].append({'source': source, 'batch_id': batch, 'manifest_valid': valid,
                                      'first_run_id_matches': metadata_ok, 'output_files': len(outputs)})
                item['files'][-1]['source_to_batch_values'] = batch_values
            observed = {p.name for p in destination.iterdir() if p.is_dir() and not p.name.startswith(('.', '_'))}
            checks.append(observed == expected_batches)
            item['batch_set_matches'] = observed == expected_batches
            if raw_frames is not None:
                cases = spark.read.parquet(str(ctx.ingestion_dir / 'parquet_files/train/train_base')).select('case_id')
                selected_raw = raw_frames[name].join(cases, 'case_id', 'left_semi')
                item['selected_raw_values'] = compare_rows(selected_raw, actual, columns)
                checks.append(item['selected_raw_values']['success'])
            item['success'] = all(checks)
            if item['success']:
                report['accepted_rows'] += row_count
        report['lineage'] = audit_lineage(ctx, lineage_path, files_index)
        report['checks'] = [item['success'] for item in report['tables'].values()] + [report['lineage']['success']]
        report['checks'].append(sha256(contract_path) == contract_hash)
        source_fingerprints(ctx.raw_dir, contract)
        report['status'] = 'passed' if all(report['checks']) else 'failed'
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
    if report['status'] != 'passed':
        report['accepted_rows'] = 0  # Falha bloqueia a publicação inteira; não há descarte/quarentena.
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if report['status'] != 'passed':
        raise RuntimeError(f'Reconciliação Bronze falhou; relatório: {path}')
    return {'json': str(path), 'status': 'passed', 'accepted_rows': report['accepted_rows'],
            'rejected_rows': 0, 'report_sha256': sha256(path)}
