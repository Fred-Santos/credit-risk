"""Publicação coerente Silver+Gold; ABT atualizada pelas chaves afetadas."""
from __future__ import annotations

from pathlib import Path

from src.gold.model import ABT_SCHEMA, MONTH_SCHEMA, affected_cases, build_abt, build_monthly
from src.gold.quality import validate_abt, validate_monthly
from src.publication.evolution import MARKER, v2_schema
from src.publication.protocol import publish_snapshot
from src.quality.contracts import check_schema
from src.quality.reconcile_bronze import compare_rows


def _require_managed(frames: dict, plan: dict):
    from pyspark.sql import functions as F
    if set(frames) != set(plan['tables']):
        raise ValueError('Silver incompleta para consumo Gold')
    for name, frame in frames.items():
        check_schema(frame, {'schema': v2_schema(plan, name)})
        if frame.filter(F.col(MARKER).isNull() | (F.col(MARKER) != 2)).limit(1).count():
            raise ValueError('Gold exige contrato Silver v2 aprovado')


def prepare_gold(tx, silver: dict, spec: dict, *, parent=None):
    from pyspark import StorageLevel
    from pyspark.sql import functions as F
    expected = build_abt(silver).persist(StorageLevel.MEMORY_AND_DISK)
    changed = None
    candidate = None
    try:
        if parent is None:
            initial = expected
            changes = {'affected_cases': silver['credit_cases'].count(), 'inserts': silver['credit_cases'].count(),
                       'updates': 0, 'mode': 'initial_full_abt'}
        else:
            old_silver = parent['silver']
            changed = affected_cases(old_silver, silver).persist(StorageLevel.MEMORY_AND_DISK)
            changes = {'affected_cases': changed.count(), 'mode': 'affected_case_recomputation'}
            initial = parent['frames']['gold.abt']
        path = tx.table_path('gold', 'abt')
        table = tx.create_table('gold', 'abt', initial)
        zero = tx.spark.read.format('delta').option('versionAsOf', 0).load(str(path))
        if not compare_rows(initial, zero, list(ABT_SCHEMA))['success']:
            raise ValueError('Cópia Gold inicial não corresponde à publicação pai')
        if changed is not None:
            candidate = build_abt(silver, changed).persist(StorageLevel.MEMORY_AND_DISK)
            initial_subset = initial.join(changed, 'case_id', 'left_semi')
            logical_rows = candidate.select(*ABT_SCHEMA).exceptAll(initial_subset.select(*ABT_SCHEMA)).count()
            logical_inserts = candidate.select('case_id').join(initial.select('case_id'), 'case_id', 'left_anti').count()
            changes.update(inserts=logical_inserts, updates=logical_rows - logical_inserts)
            current = tx.verify_owned(path, 'gold.abt').toDF()
            current_subset = current.join(changed, 'case_id', 'left_semi')
            different = candidate.select(*ABT_SCHEMA).exceptAll(current_subset.select(*ABT_SCHEMA)).select('case_id')
            incoming = candidate.join(different, 'case_id', 'left_semi').persist(StorageLevel.MEMORY_AND_DISK)
            try:
                rows = incoming.count()
                inserts = incoming.select('case_id').join(current.select('case_id'), 'case_id', 'left_anti').count()
                changes['commits_this_attempt'] = {'inserts': inserts, 'updates': rows - inserts}
                if rows:
                    with tx.commit('gold.abt', 'merge'):
                        (table.alias('t').merge(incoming.alias('s'), 't.case_id = s.case_id')
                         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
                    actual = table.history(1).first().operationMetrics
                    if int(actual['numTargetRowsInserted']) != inserts or int(actual['numTargetRowsUpdated']) != rows - inserts:
                        raise ValueError('Commit ABT diverge das chaves afetadas medidas')
            finally:
                incoming.unpersist()
            months = (parent['frames']['gold.abt'].join(changed, 'case_id', 'left_semi').select('MONTH')
                      .unionByName(expected.join(changed, 'case_id', 'left_semi').select('MONTH')).distinct())
            changes['affected_months'] = [r.MONTH for r in months.orderBy('MONTH').collect()]
        abt = tx.record_table('gold', 'abt', spec['schemas']['abt'], ['case_id'])
        proof = compare_rows(expected, abt, list(ABT_SCHEMA))
        if not proof['success']:
            raise ValueError(f'ABT incremental diverge da recomputação integral: {proof}')
        tx.validations['abt_full_recomputation'] = {'status': 'passed', **proof}
        tx.validations['abt_contract_and_sql_oracle'] = validate_abt(abt, silver, spec)
        tx.details['gold_update'] = changes
        tx.hook('after_abt_quality')
        # Poucos períodos: materializar a consulta completa elimina resultados de
        # meses que ficaram vazios e atualiza períodos antigos sem DML parcial.
        monthly_expected = build_monthly(abt).persist(StorageLevel.MEMORY_AND_DISK)
        try:
            monthly_table = tx.create_table('gold', 'monthly_metrics', monthly_expected)
            monthly = tx.record_table('gold', 'monthly_metrics', spec['schemas']['monthly_metrics'], ['MONTH'])
            monthly_proof = compare_rows(monthly_expected, monthly, list(MONTH_SCHEMA))
            if not monthly_proof['success']:
                raise ValueError('Indicadores persistidos divergem do SQL da ABT')
            tx.validations['monthly_contract_and_silver_oracle'] = validate_monthly(monthly, abt, silver, spec)
            tx.validations['monthly_delta_readback'] = {'status': 'passed', **monthly_proof}
            tx.details['indicator_strategy'] = 'full_sql_materialization_per_publication_after_incremental_abt'
            tx.hook('after_gold_quality')
        finally:
            monthly_expected.unpersist()
    finally:
        expected.unpersist()
        if changed is not None:
            changed.unpersist()
        if candidate is not None:
            candidate.unpersist()


def publish_analytics(ctx, spark, registry: Path, *, source_manifest: dict, source_registry: Path,
                      plan: dict, spec: dict, fingerprints: dict, parent=None, hook=None):
    from src.pipelines.download_home_credit import sha256
    from src.publication.protocol import verify_manifest
    actual_source, source_frames = verify_manifest(ctx.repo_root, source_registry, source_manifest['publication_id'], spark)
    if (actual_source != source_manifest or actual_source['identity']['scope'] != 'silver_v2'
            or set(source_frames) != {'silver.' + n for n in plan['tables']}):
        raise ValueError('Entrada Gold não corresponde à publicação Silver v2 aprovada')
    silver = {n: source_frames['silver.' + n] for n in plan['tables']}
    _require_managed(silver, plan)
    source_path = source_registry / 'manifests' / (source_manifest['publication_id'] + '.json')
    reference = {'manifest': source_path.relative_to(ctx.repo_root).as_posix(), 'sha256': sha256(source_path)}
    parent_ref = None
    if parent is not None:
        actual_parent, parent_frames = verify_manifest(ctx.repo_root, registry, parent['manifest']['publication_id'], spark)
        if actual_parent != parent['manifest'] or actual_parent['identity']['scope'] != 'analytics_v1':
            raise ValueError('Publicação analítica pai inválida')
        parent = {'manifest': actual_parent, 'frames': parent_frames,
                  'silver': {n: parent_frames['silver.' + n] for n in plan['tables']}}
        p = registry / 'manifests' / (parent['manifest']['publication_id'] + '.json')
        parent_ref = {'manifest': p.relative_to(ctx.repo_root).as_posix(), 'sha256': sha256(p)}
    identity = {'scope': 'analytics_v1', 'selection_id': source_manifest['identity']['selection_id'],
        'silver_publication': reference, 'parent_analytics': parent_ref,
        'gold_contract_sha256': spec['contract_sha256'], 'code_and_configuration': fingerprints,
        'spark_version': spark.version}

    def build(tx):
        # As referências Silver são imutáveis e já aprovadas: não fazer outra cópia.
        tx.entries.update(source_manifest['tables'])
        tx.validations['silver_input'] = {'status': 'passed', 'source_publication_id': source_manifest['publication_id'],
                                         'managed_contract_version': 2}
        tx.details['references'] = [reference] + ([parent_ref] if parent_ref is not None else [])
        tx.hook('between_silver_and_gold')
        prepare_gold(tx, silver, spec, parent=parent)

    return publish_snapshot(ctx, registry, spark, identity, fingerprints, build, hook=hook)
