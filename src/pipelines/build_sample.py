"""Recorte imutável e determinístico; não altera a RAW nem executa Bronze/Silver."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

import yaml

from src.pipelines.download_home_credit import sha256
from src.quality.contracts import load_contract, read_source_frames, source_fingerprints, validate_snapshot
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session


def load_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text(encoding='utf-8'))
    fields = {'version', 'algorithm', 'seed', 'max_cases', 'week_min', 'week_max', 'batches'}
    if not isinstance(policy, dict) or set(policy) != fields or policy['version'] != 1:
        raise ValueError('Política deve conter exatamente os campos da versão 1')
    if policy['algorithm'] != 'sha256_seed_colon_case_id_v1':
        raise ValueError('Algoritmo de seleção não suportado')
    if not isinstance(policy['seed'], str) or not policy['seed'].strip():
        raise ValueError('seed deve ser string não vazia')
    if type(policy['max_cases']) is not int or not 1 <= policy['max_cases'] <= 50000:
        raise ValueError('max_cases deve estar entre 1 e 50000 no MVP')
    if any(type(policy[k]) is not int for k in ('week_min', 'week_max')) or not 0 <= policy['week_min'] <= policy['week_max']:
        raise ValueError('Intervalo de semanas inválido')
    if not isinstance(policy['batches'], list) or not policy['batches']:
        raise ValueError('Defina ao menos um lote')
    cursor, identifiers = policy['week_min'], set()
    for batch in policy['batches']:
        if not isinstance(batch, dict) or set(batch) != {'id', 'min_week', 'max_week'}:
            raise ValueError('Campos de lote inválidos')
        if not isinstance(batch['id'], str) or not re.fullmatch(r'[a-z][a-z0-9_]*', batch['id']) or batch['id'] in identifiers:
            raise ValueError('Identificador de lote inválido ou repetido')
        if any(type(batch[k]) is not int for k in ('min_week', 'max_week')):
            raise ValueError('Semanas de lote devem ser inteiros')
        if batch['min_week'] != cursor or batch['max_week'] < cursor:
            raise ValueError('Lotes devem cobrir o intervalo em ordem, sem lacunas ou sobreposição')
        cursor = batch['max_week'] + 1
        identifiers.add(batch['id'])
    if cursor != policy['week_max'] + 1:
        raise ValueError('Lotes não cobrem todo o intervalo configurado')
    return policy


def select_cases(base, policy: dict):
    from pyspark.sql import functions as F

    # Entrada já validada: case_id único/não nulo. target não participa da seleção.
    ranked = base.select('case_id', 'WEEK_NUM').withColumn(
        '_selection_hash', F.sha2(F.concat(F.lit(policy['seed'] + ':'), F.col('case_id').cast('string')), 256))
    selected = ranked.orderBy('_selection_hash', 'case_id').limit(policy['max_cases']).drop('_selection_hash')
    assignment = F.lit(None).cast('string')
    for batch in reversed(policy['batches']):
        assignment = F.when(F.col('WEEK_NUM').between(batch['min_week'], batch['max_week']), F.lit(batch['id'])).otherwise(assignment)
    return selected.withColumn('_batch_id', assignment)


def case_digest(frame) -> str:
    digest = hashlib.sha256()
    for row in frame.select('case_id').orderBy('case_id').toLocalIterator():
        digest.update(f'{row.case_id}\n'.encode('ascii'))
    return digest.hexdigest()


def _file_checksums(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.suffix in {'.parquet', '.csv'}}


def verify_committed(root: Path, identity: dict) -> dict:
    path = root / '_selection.json'
    if not path.is_file():
        raise RuntimeError('Recorte existente sem manifesto de publicação')
    manifest = json.loads(path.read_text())
    if manifest['identity'] != identity or manifest['output_checksums'] != _file_checksums(root):
        raise RuntimeError('Identidade ou conteúdo do recorte alterado; não será sobrescrito')
    return manifest


def build_sample(ctx, spark, contract_path: Path, policy_path: Path) -> dict:
    import fcntl
    from pyspark import StorageLevel

    contract, policy = load_contract(contract_path), load_policy(policy_path)
    sources = source_fingerprints(ctx.raw_dir, contract)
    code_paths = ['src/pipelines/build_sample.py', 'src/quality/contracts.py',
                  'src/profiling/frame_profile.py', 'src/utils/spark.py',
                  'configs/spark.yaml', 'requirements.lock']
    identity = {
        'contract_sha256': sha256(contract_path), 'policy_sha256': sha256(policy_path),
        'sources': sources, 'spark_version': spark.version,
        'implementation_sha256': {name: sha256(ctx.repo_root / name) for name in code_paths},
    }
    identity_digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    selection_id = identity_digest[:24]
    root = ctx.sample_dir
    root.mkdir(parents=True, exist_ok=True)
    destination = root / selection_id
    with (root / '.selection.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frames = read_source_frames(spark, ctx.raw_dir, contract)
        if not destination.exists():
            source_validation = validate_snapshot(frames, contract)
            if source_validation['status'] != 'passed':
                failed = [r for r in source_validation['checks'] if not r['success']]
                raise RuntimeError(f'Snapshot de origem reprovado: {failed}')
        selected = select_cases(frames['train_base'], policy).persist(StorageLevel.MEMORY_AND_DISK)
        stage = root / '.staging' / f'{selection_id}-{ctx.run_id}'
        try:
            selected_count = selected.count()
            if selected.filter('_batch_id is null').limit(1).count():
                raise ValueError('Há casos selecionados fora dos lotes; revise a política')
            selected_digest = case_digest(selected)
            if destination.exists():
                manifest = verify_committed(destination, identity)
                stored = spark.read.parquet(str(destination / 'parquet_files/train/train_base'))
                if selected_digest != manifest['case_set_sha256'] or case_digest(stored) != selected_digest:
                    raise RuntimeError('Reexecução selecionou um conjunto diferente de casos')
                source_fingerprints(ctx.raw_dir, contract)
                return {'selection_id': selection_id, 'path': str(destination),
                        'reused': True, 'case_count': selected_count, 'case_set_sha256': selected_digest}
            stage.mkdir(parents=True, exist_ok=False)
            keys = selected.select('case_id')
            counts = {}
            for name, frame in frames.items():
                sample = frame.join(keys, 'case_id', 'left_semi').select(*frame.columns)
                path = stage / 'parquet_files' / 'train' / name
                sample.coalesce(1).write.mode('errorifexists').parquet(str(path))
                saved = spark.read.parquet(str(path))
                # Compara valores, inclusive multiplicidade; contagem isolada não basta.
                columns = frame.columns
                if (sample.select(*columns).exceptAll(saved.select(*columns)).limit(1).count()
                        or saved.select(*columns).exceptAll(sample.select(*columns)).limit(1).count()):
                    raise RuntimeError(f'Reconciliação de valores falhou: {name}')
                counts[name] = saved.count()
            selected.coalesce(1).write.parquet(str(stage / 'case_batches'))
            shutil.copyfile(ctx.raw_dir / 'feature_definitions.csv', stage / 'feature_definitions.csv')
            saved_frames = {name: spark.read.parquet(str(stage / 'parquet_files/train' / name)) for name in frames}
            validation = validate_snapshot(saved_frames, contract)
            if validation['status'] != 'passed' or counts['train_base'] != selected_count:
                raise RuntimeError('Recorte reprovado pelo contrato ou contagem de casos')
            batches = []
            for batch in policy['batches']:
                batch_keys = selected.filter(selected['_batch_id'] == batch['id']).select('case_id')
                batches.append({**batch, 'cases': batch_keys.count(),
                                'rows': {name: frame.join(batch_keys, 'case_id', 'left_semi').count()
                                         for name, frame in saved_frames.items()}})
            if (sum(batch['cases'] for batch in batches) != selected_count
                    or any(sum(batch['rows'][name] for batch in batches) != count
                           for name, count in counts.items())):
                raise RuntimeError('Lotes não reconciliam com o snapshot selecionado')
            source_fingerprints(ctx.raw_dir, contract)  # Detecta alteração durante a execução.
            manifest = {
                'selection_id': selection_id, 'identity_sha256': identity_digest,
                'identity': identity, 'first_run_id': ctx.run_id,
                'created_at_utc': ctx.started_at_utc, 'case_count': selected_count,
                'case_set_sha256': selected_digest, 'counts': counts, 'batches': batches,
                'policy': policy, 'source_validation': source_validation,
                'sample_validation': validation, 'output_checksums': _file_checksums(stage),
                'reconciliation': 'equal_values_and_multiplicity_in_both_directions',
                'arrival_kind': 'simulated_batch_assignment_not_real_cdc',
            }
            (stage / '_selection.json').write_text(json.dumps(manifest, indent=2, default=str) + '\n')
            stage.rename(destination)
            return {'selection_id': selection_id, 'path': str(destination), 'reused': False,
                    'case_count': selected_count, 'case_set_sha256': selected_digest,
                    'counts': counts, 'batches': batches}
        finally:
            selected.unpersist()
            shutil.rmtree(stage, ignore_errors=True)


def main():
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    spark = create_spark_session(ctx.repo_root, app_name='credit-risk-build-sample')
    try:
        result = build_sample(ctx, spark, ctx.repo_root / 'configs/contracts/home_credit_v1.yaml',
                              ctx.repo_root / 'configs/sample_policy.yaml')
    finally:
        spark.stop()
    output = ctx.repo_root / 'artifacts' / 'samples' / f'{ctx.run_id}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
