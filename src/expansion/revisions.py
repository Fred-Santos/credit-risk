"""Revisões simuladas por chave para qualquer tabela; snapshots pais imutáveis."""
import json
from pathlib import Path
import uuid
from functools import reduce
from pyspark.sql import functions as F,Window
from src.bronze.build_bronze import _ingestion_lock
from src.expansion.silver import load_contract,open_silver
from src.expansion.quality import check_schema,key_audit,compare_keyed,validate_silver
from src.expansion.storage import digest,verify_package,finish_package,pin_delta,open_pin,safe_path
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def choose_events(frame,parent,key):
    """Duplicatas idênticas são reenvios; mesma chave/revisão divergente bloqueia."""
    check_schema(frame,dict(parent.dtypes))
    distinct=frame.dropDuplicates(frame.columns)
    conflicts=distinct.groupBy(*key,'_source_revision').count().where('count > 1').limit(1).count()
    if conflicts:raise ValueError('Payloads conflitantes na mesma chave/revisão')
    window=Window.partitionBy(*key).orderBy(F.desc('_source_revision'))
    chosen=distinct.withColumn('__rank',F.row_number().over(window)).where('__rank=1').drop('__rank')
    key_audit(chosen,key)
    e,p=distinct.alias('e'),parent.alias('p')
    matched=e.join(p,key,'inner')
    different=reduce(lambda a,b:a|b,[~F.col('e.'+c).eqNullSafe(F.col('p.'+c)) for c in frame.columns if c not in key],F.lit(False))
    if matched.where((F.col('e._source_revision')==F.col('p._source_revision')) & different).limit(1).count():
        raise ValueError('Revisão existente com outro payload')
    old=parent.select(*key,F.col('_source_revision').alias('__parent_revision'))
    return chosen.join(old,key,'left').where(F.col('__parent_revision').isNull() |
         (F.col('_source_revision')>F.col('__parent_revision'))).drop('__parent_revision')


def apply_revision(repo,spark,parent_path,contract_path,event_manifest_path):
    from delta.tables import DeltaTable
    contract=load_contract(contract_path)
    parent,frames=open_silver(repo,spark,parent_path)
    event=json.loads(event_manifest_path.read_text())
    if event.get('is_simulated') is not True:raise ValueError('Este protocolo exige simulação declarada')
    if not set(event['tables'])<=set(frames):raise ValueError('Fonte de evento desconhecida')
    sources={}
    for name,entry in event['tables'].items():
        path=safe_path(repo,entry['path'])
        files={p.relative_to(path).as_posix():sha256(p) for p in sorted(path.glob('*.parquet'))}
        if files!=entry['files']:raise ValueError('Evento alterado')
        sources[name]=spark.read.parquet(str(path))
    identity={'scope':'expansion_silver_revision_v1','parent_manifest_sha256':sha256(parent_path/'_silver.json'),
        'parent_id':parent['id'],'events_manifest_sha256':sha256(event_manifest_path),
        'contract_sha256':sha256(contract_path),'implementation':sha256(Path(__file__))}
    identifier=digest(identity)[:24]
    namespace=repo/'data/silver/expansion';dest=namespace/identifier
    with _ingestion_lock(namespace):
        if dest.exists():return verify_package(dest,'_silver.json',identity),True
        stage=namespace/'.staging'/uuid.uuid4().hex;stage.mkdir(parents=True)
        manifest={'id':identifier,'identity':identity,'identity_sha256':digest(identity),'status':'running',
            'tables':dict(parent['tables']),'population':parent['population'],'validation':{},
            'parent_id':parent['id'],'is_simulated':True,'changed_sources':[],
            'dependency_rule':'case_ids_in_any_changed_auxiliary_or_base_and_old_new_months'}
        affected=[]
        base=frames['train_base'].select('case_id')
        try:
            for name,events in sources.items():
                rule=contract['tables'][name]
                event_rule={**rule,'key':rule['key']+['_source_revision']}
                validate_silver(events.dropDuplicates(events.columns),event_rule,base)
                if events.where(~F.col('_is_simulated')).limit(1).count():raise ValueError('Evento sem flag de simulação')
                candidate=choose_events(events,frames[name],rule['key'])
                count=candidate.count()
                if not count:continue
                if name=='train_base':
                    # Janelas continuam fixadas pelo contrato/identidade Bronze do pai.
                    if candidate.where("date_decision < DATE '2020-01-01' OR date_decision >= DATE '2020-10-01'").limit(1).count():
                        raise ValueError('Caso fora da coorte temporal')
                target=stage/'tables'/name
                frames[name].write.format('delta').mode('errorifexists').save(str(target))
                condition=' AND '.join(f't.`{k}` = e.`{k}`' for k in rule['key'])
                DeltaTable.forPath(spark,str(target)).alias('t').merge(candidate.alias('e'),condition).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
                updated=spark.read.format('delta').load(str(target))
                quality=validate_silver(updated,rule,base)
                # Oráculo independente do MERGE: remove as chaves candidatas e une os novos valores.
                oracle=frames[name].join(candidate.select(*rule['key']),rule['key'],'left_anti').unionByName(candidate)
                key_audit(oracle,rule['key'])
                proof=compare_keyed(oracle,updated,rule['key'])
                if not proof['success']:raise ValueError('Revisão diverge de reconstrução integral')
                manifest['tables'][name]=pin_delta(spark,target,str((dest/'tables'/name).relative_to(repo)),quality['rows'])
                manifest['validation'][name]={'quality':quality,'preservation':proof,'changed_rows':count}
                manifest['changed_sources'].append(name)
                affected.append(candidate.select('case_id'))
            ids=base.limit(0) if not affected else reduce(lambda a,b:a.unionByName(b),affected).distinct()
            ids.write.parquet(str(stage/'affected_cases'))
            # Somente períodos agregados pequenos são coletados; IDs permanecem em Parquet.
            new_base=open_pin(repo,spark,manifest['tables']['train_base']) if 'train_base' not in manifest['changed_sources'] else spark.read.format('delta').load(str(stage/'tables/train_base'))
            if 'train_base' in manifest['changed_sources']:
                manifest['population']={**parent['population'],'windows':{}}
                for label,start,end in [('development','2020-01-01','2020-06-01'),('evaluation','2020-06-01','2020-10-01'),('public','2020-01-01','2020-10-01')]:
                    manifest['population']['windows'][label]=new_base.where(f"date_decision >= DATE '{start}' AND date_decision < DATE '{end}'").count()
            months=frames['train_base'].join(ids,'case_id','left_semi').select('MONTH').unionByName(
                new_base.join(ids,'case_id','left_semi').select('MONTH')).distinct().orderBy('MONTH')
            manifest['affected_cases']={'path':str((dest/'affected_cases').relative_to(repo)),'rows':ids.count(),
                'old_new_months':[r[0] for r in months.collect()]}
            return finish_package(stage,dest,manifest,'_silver.json'),False
        except BaseException as exc:
            manifest.update(status='failed',error_type=type(exc).__name__);atomic_json(stage/'_progress.json',manifest);raise
