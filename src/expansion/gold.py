"""ABTs compostas por features e rótulos separados, pinadas a todas as Silver."""
import json
from pathlib import Path
import uuid
import time
import yaml
from pyspark.sql import functions as F
from src.bronze.build_bronze import _ingestion_lock
from src.expansion.features import META,load_features,aggregate_block,sql_oracle,block_schema,feature_catalog
from src.expansion.silver import load_contract,open_silver
from src.expansion.quality import check_schema,key_audit,compare_keyed
from src.expansion.storage import digest,finish_package,verify_package,pin_delta,open_pin
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def assemble(base,blocks,catalog):
    result=base.select(*META)
    for block in blocks.values():result=result.join(block,'case_id','left')
    fill={f['name']:False if f['type']=='boolean' else 0 for f in catalog['features']
          if f['null_policy']=='zero_count_or_false_flag_when_no_source'}
    return result.fillna(fill).select(*META,*[f['name'] for f in catalog['features']])


def validate_feature_values(frame,catalog):
    bad=F.lit(False)
    for spec in catalog['features']:
        c=F.col(spec['name'])
        if spec['type'] in ('float','double'):bad=bad|F.isnan(c)|(F.abs(c)==float('inf'))
        if spec['null_policy']=='zero_count_or_false_flag_when_no_source':bad=bad|c.isNull()
    if frame.where(bad).limit(1).count():raise ValueError('Feature não finita ou contagem/flag nula')
    if 'target' in frame.columns:raise ValueError('Rótulo misturado aos atributos')


def build_gold(repo,spark,silver_path,contract_path,feature_path,gold_contract_path,policy,*,audit_path):
    contract=load_contract(contract_path);config=load_features(feature_path,contract)
    catalog=yaml.safe_load(gold_contract_path.read_text())
    if (catalog['silver_contract_sha256']!=sha256(contract_path) or catalog['feature_policy_sha256']!=sha256(feature_path)
            or catalog['eligible_predictors'] or catalog['ml_ready']
            or any(f['ml_eligible'] for f in catalog['features'])):
        raise ValueError('Contrato Gold ou aprovação temporal divergentes')
    expected_catalog=feature_catalog(config,contract,{f['source_column']:f['description'] for f in catalog['features'] if f['source_column']})
    indexed={f['name']:f for f in catalog['features']}
    if (len(indexed)!=len(catalog['features']) or indexed!={f['name']:f for f in expected_catalog['features']}):
        raise ValueError('Fórmulas/nomes de atributos divergentes')
    silver,frames=open_silver(repo,spark,silver_path)
    audit=json.loads(audit_path.read_text())
    if audit['silver_manifest_sha256']!=sha256(silver_path/'_silver.json') or audit['status']!='passed':
        raise ValueError('Auditoria temporal não corresponde à Silver')
    identity={'scope':'expansion_temporal_abts_v1','silver_manifest_sha256':sha256(silver_path/'_silver.json'),
        'silver_id':silver['id'],'gold_contract_sha256':sha256(gold_contract_path),'policy':policy,
        'temporal_audit_sha256':sha256(audit_path),'implementation':{p.name:sha256(p) for p in
            [Path(__file__),Path(__file__).with_name('features.py'),Path(__file__).with_name('quality.py'),Path(__file__).with_name('storage.py')]}}
    identifier=digest(identity)[:24]
    namespace=repo/'data/gold/expansion';namespace.mkdir(parents=True,exist_ok=True)
    dest=namespace/identifier
    with _ingestion_lock(namespace):
        if dest.exists():return verify_package(dest,'_gold.json',identity),True
        stage=namespace/'.staging'/uuid.uuid4().hex;stage.mkdir(parents=True)
        manifest={'id':identifier,'identity':identity,'identity_sha256':digest(identity),'status':'running',
            'blocks':{},'products':{},'validation':{},'feature_schema':{**META,**{f['name']:f['type'] for f in catalog['features']}},
            'label_schema':catalog['label_schema'],'eligible_predictors':[],'ml_ready':False,
            'temporal_limitations':{'available_at':'unproven','target_maturation':'unknown','person_overlap':'not_verifiable'},
            'label_access':'evaluation_labels_require_explicit_opt_in_no_filesystem_security_claim',
            'preprocessing':'none_fitted','dependencies':silver['tables']}
        blocks={};started=time.monotonic();wide=None
        try:
            for table,rule in config['sources'].items():
                block=aggregate_block(frames[table],table,rule,contract['tables'][table])
                key_audit(block,['case_id'])
                target=stage/'blocks'/table
                block.write.format('delta').mode('errorifexists').save(str(target))
                actual=spark.read.format('delta').load(str(target))
                check_schema(actual,block_schema(table,rule,contract['tables'][table]))
                quality=key_audit(actual,['case_id'])
                oracle=sql_oracle(spark,frames[table],table,rule,contract['tables'][table])
                key_audit(oracle,['case_id'])
                tolerance=config['float_comparison']
                proof=compare_keyed(oracle,actual,['case_id'],numeric_tolerance=(tolerance['absolute'],tolerance['relative']))
                if not proof['success']:raise ValueError('Bloco diverge do SQL independente: '+table)
                manifest['blocks'][table]=pin_delta(spark,target,str((dest/'blocks'/table).relative_to(repo)),quality['rows'])
                manifest['validation'][table]=proof
                blocks[table]=actual
                atomic_json(stage/'_progress.json',manifest)
                print('Gold bloco aprovado:',table,flush=True)
            wide=assemble(frames['train_base'],blocks,catalog).cache()
            check_schema(wide,manifest['feature_schema']);quality=key_audit(wide,['case_id'])
            validate_feature_values(wide,catalog)
            if quality['rows']!=silver['population']['selected_cases']:raise ValueError('População alterada no join Gold')
            frames['train_base'].createOrReplaceTempView('base_abt_oracle')
            keys={}
            for name in ('development','evaluation'):
                window=policy['windows'][name]
                predicate=f"date_decision >= DATE '{window['start_inclusive']}' AND date_decision < DATE '{window['end_exclusive']}'"
                selected=wide.where(predicate)
                table_path=stage/'products'/name/'features'
                selected.write.format('delta').mode('errorifexists').save(str(table_path))
                actual=spark.read.format('delta').load(str(table_path))
                check_schema(actual,manifest['feature_schema']);q=key_audit(actual,['case_id'])
                labels=frames['train_base'].where(predicate).select('case_id','target')
                label_path=stage/'products'/name/'labels'
                labels.write.format('delta').mode('errorifexists').save(str(label_path))
                label_actual=spark.read.format('delta').load(str(label_path))
                key_audit(label_actual,['case_id'])
                label_proof=compare_keyed(labels,label_actual,['case_id'])
                # Oráculo de população em SQL na base Silver, independente do filtro DataFrame.
                oracle=spark.sql('SELECT case_id, date_decision, MONTH, WEEK_NUM FROM base_abt_oracle WHERE '+predicate)
                pop_proof=compare_keyed(oracle,actual.select(*META),['case_id'])
                # Readback integral de todas as features, inclusive nulos e contagens de cobertura.
                feature_proof=compare_keyed(selected,actual,['case_id'])
                if not all(p['success'] for p in (label_proof,pop_proof,feature_proof)) or q['rows']!=silver['population']['windows'][name]:
                    raise ValueError('ABT/rótulos não reconciliados: '+name)
                if label_actual.join(actual.select('case_id'),'case_id','left_anti').count():raise ValueError('Rótulo fora da população')
                manifest['products'][name]={'window':window,
                    'features':pin_delta(spark,table_path,str((dest/'products'/name/'features').relative_to(repo)),q['rows']),
                    'labels':pin_delta(spark,label_path,str((dest/'products'/name/'labels').relative_to(repo)),q['rows']),
                    'proofs':{'population':pop_proof,'features':feature_proof,'labels':label_proof},
                    'label_counts':[r.asDict() for r in label_actual.groupBy('target').count().orderBy('target').collect()]}
                keys[name]=actual.select('case_id')
            if keys['development'].join(keys['evaluation'],'case_id').count():raise ValueError('Casos sobrepostos')
            union=keys['development'].unionByName(keys['evaluation'])
            key_audit(union,['case_id'])
            public_proof=compare_keyed(frames['train_base'].select('case_id'),union,['case_id'])
            if not public_proof['success']:raise ValueError('União não preserva população pública')
            manifest.update(public_population_proof=public_proof,case_intersection=0,duration_seconds=round(time.monotonic()-started,3))
            return finish_package(stage,dest,manifest,'_gold.json'),False
        except BaseException as exc:
            manifest.update(status='failed',error_type=type(exc).__name__);atomic_json(stage/'_progress.json',manifest);raise
        finally:
            if wide is not None:wide.unpersist()


def open_abt(repo,spark,path,population,*,include_labels=False,allow_evaluation_labels=False):
    if population not in ('development','evaluation'):raise ValueError('População desconhecida')
    manifest=verify_package(path,'_gold.json')
    if include_labels and population=='evaluation' and not allow_evaluation_labels:
        raise PermissionError('Rótulos da reserva exigem opt-in explícito')
    product=manifest['products'][population]
    result=open_pin(repo,spark,product['features'])
    if include_labels:result=result.join(open_pin(repo,spark,product['labels']),'case_id','inner')
    return result


def open_ml_inputs(repo,spark,path,population):
    manifest=verify_package(path,'_gold.json')
    if not manifest['ml_ready'] or not manifest['eligible_predictors']:
        raise ValueError('Treino bloqueado: disponibilidade temporal e maturação do rótulo não comprovadas')
    return open_abt(repo,spark,path,population).select('case_id',*manifest['eligible_predictors'])
