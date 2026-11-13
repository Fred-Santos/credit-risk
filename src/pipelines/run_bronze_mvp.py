"""Orquestra ingestão Bronze com entrada explícita e gate de conclusão local."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from src.bronze.build_bronze import build_bronze_from_raw, _ingestion_lock, _source_record
from src.bronze.inputs import BronzeInput, bind_raw, bind_sample, verify_input
from src.governance.inventory_bronze import build_bronze_inventory
from src.lineage.lineage_bronze import emit_bronze_lineage
from src.observability.metrics_bronze import record_bronze_metrics
from src.pipelines.download_home_credit import sha256
from src.quality.checks_bronze import run_bronze_checks
from src.quality.reconcile_bronze import reconcile_bronze
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def _bind_output(root: Path, descriptor: dict):
    binding = root / '_input.json'
    if binding.exists():
        if json.loads(binding.read_text()) != descriptor:
            raise RuntimeError('Namespace Bronze já está vinculado a outra entrada')
    else:
        if any(root.rglob('*.parquet')):
            raise RuntimeError('Bronze existente sem vínculo de entrada; use namespace novo após revisão')
        _write_json(binding, descriptor)


def _output_index(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): _source_record(p, root)['sha256']
            for p in sorted(root.rglob('*')) if p.is_file()
            and (p.suffix == '.parquet' or p.name in {'_ingestion.json', '_input.json'})}


def run_bronze(bound: BronzeInput, spark) -> dict:
    ctx = bound.ctx
    root = ctx.bronze_dir
    root.mkdir(parents=True, exist_ok=True)
    ready = root / '_READY.json'
    report_path = ctx.docs_root / 'runs' / f'{ctx.run_id}.json'
    quality_config = ctx.repo_root / 'configs/quality_rules_bronze.yaml'
    quality_hash = sha256(quality_config)
    started = time.perf_counter()
    report = {
        'run_id': ctx.run_id, 'started_at_utc': ctx.started_at_utc,
        'status': 'running', 'input': bound.descriptor,
        'bronze_dir': root.relative_to(ctx.repo_root).as_posix(),
        'spark_version': spark.version, 'quality_config_sha256': quality_hash,
        'code_sha256': {name: sha256(ctx.repo_root / name)
                       for name in ('src/bronze/build_bronze.py', 'src/bronze/inputs.py',
                                    'src/pipelines/run_bronze_mvp.py', 'src/quality/engine.py',
                                    'src/quality/bronze_contract.py',
                                    'src/quality/reconcile_bronze.py',
                                    'src/utils/run_context.py')
                       if (ctx.repo_root / name).is_file()},
    }
    # Este lock cobre materialização, qualidade e conclusão; o build tem lock próprio.
    with _ingestion_lock(root, '.pipeline.lock'):
        _bind_output(root, bound.descriptor)
        ready.unlink(missing_ok=True)
        _write_json(report_path, report)
        try:
            verify_input(bound)
            report['written_datasets'] = build_bronze_from_raw(ctx, spark)
            report['quality'] = run_bronze_checks(ctx, spark)
            datasets = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(('.', '_')))
            counts = {p.name: spark.read.parquet(str(p)).count() for p in datasets}
            if not counts:
                raise RuntimeError('Nenhum dataset Bronze disponível após materialização')
            if bound.expected_counts is not None and counts != bound.expected_counts:
                raise RuntimeError(f'Contagens Bronze divergem do recorte: {counts}')
            report['counts'] = counts
            report['metrics'] = record_bronze_metrics(ctx, spark=spark, include_row_counts=True)
            report['lineage'] = emit_bronze_lineage(ctx, include_checksums=True)
            report['reconciliation'] = reconcile_bronze(ctx, spark, lineage_path=Path(report['lineage']['json']))
            report['inventory'] = build_bronze_inventory(ctx)
            verify_input(bound)
            if quality_hash != sha256(quality_config):
                raise RuntimeError('Regras de qualidade mudaram durante a execução')
            report.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          duration_seconds=round(time.perf_counter() - started, 3),
                          ready_path=ready.relative_to(ctx.repo_root).as_posix())
            _write_json(report_path, report)
            _write_json(ready, {
                'format_version': 1, 'status': 'passed', 'verified_by_run_id': ctx.run_id,
                'input': bound.descriptor, 'counts': counts,
                'output_checksums': _output_index(root),
                'quality_config_sha256': quality_hash,
                'quality_report_sha256': sha256(Path(report['quality']['json'])),
                'reconciliation_report_sha256': report['reconciliation']['report_sha256'],
                'run_report': report_path.relative_to(ctx.repo_root).as_posix(),
            })
        except BaseException as error:
            ready.unlink(missing_ok=True)
            report.update(status='failed', error_type=type(error).__name__, error=str(error),
                          finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          duration_seconds=round(time.perf_counter() - started, 3))
            _write_json(report_path, report)
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--sample', metavar='SELECTION_ID', help='Recorte publicado de data/samples')
    group.add_argument('--raw', action='store_true', help='Modo explícito de ingestão da RAW configurada')
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    bound = bind_sample(ctx, args.sample) if args.sample else bind_raw(ctx)
    if not (bound.ctx.ingestion_dir / 'parquet_files/train').exists():
        raise RuntimeError('Diretório de treino da entrada não existe')
    spark = create_spark_session(ctx.repo_root, app_name='credit-risk-bronze-mvp')
    try:
        print(json.dumps(run_bronze(bound, spark), indent=2))
    finally:
        spark.stop()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Cancelado pelo usuário.', file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f'ERRO: {error}', file=sys.stderr)
        raise SystemExit(1)
