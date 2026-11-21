"""Silver Delta de todas as fontes; reconciliação exata após cast ISO aprovado."""
import json
from pathlib import Path
import time
import uuid
import yaml
from pyspark.sql import functions as F
from src.bronze.build_bronze import _ingestion_lock
from src.bronze.expansion import verify_committed
from src.expansion.quality import check_schema, key_audit, compare_keyed, validate_silver
from src.expansion.storage import digest, finish_package, verify_package, pin_delta, open_pin
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def load_contract(path):
    spec=yaml.safe_load(Path(path).read_text())
    if (spec['version']!=1 or spec['scope']!='expansion_silver_retrospective'
            or spec['date_policy']!='strict_iso_roundtrip_zero_loss'
            or spec['future_dates']!='preserve_not_availability_evidence'
            or spec['failure_policy']!='block_entire_snapshot_preserve_input'):
        raise ValueError('Contrato Silver não suportado')
    for name,t in spec['tables'].items():
        if t['source_table']!=name or not set(t['key'])<=set(t['input_schema']):
            raise ValueError('Chave/mapeamento inválidos')
        expected={c:'date' if c in t['date_columns'] else typ for c,typ in t['input_schema'].items()}
        expected.update(_source_revision='bigint',_is_simulated='boolean')
        if t['schema']!=expected or any(t['input_schema'].get(c)!='string' for c in t['date_columns']):
            raise ValueError('Conversão fora do contrato')
    return spec


def transform(frame,spec):
    check_schema(frame,spec['input_schema'])
    invalid=F.lit(False);expressions={}
    for c in spec['date_columns']:
        parsed=F.try_to_timestamp(c,F.lit('yyyy-MM-dd')).cast('date')
        invalid=invalid | (F.col(c).isNotNull() & (parsed.isNull() | (F.date_format(parsed,'yyyy-MM-dd')!=F.col(c))))
        expressions[c]=parsed
    invalid_count=frame.where(invalid).count() if spec['date_columns'] else 0
    if invalid_count:raise ValueError(f'{invalid_count} registros com datas inválidas; nenhum será descartado')
    result=frame.select(*[expressions[c].alias(c) if c in expressions else F.col(c) for c in frame.columns])
    return result.withColumn('_source_revision',F.lit(1).cast('long')).withColumn('_is_simulated',F.lit(False))


def build_silver(repo,spark,bronze,contract_path,*,fail_after_table=None):
    spec=load_contract(contract_path)
    original=json.loads((bronze/'_bronze.json').read_text())
    approved=verify_committed(bronze,original['identity'])
    if set(spec['tables'])!=set(approved['tables']):raise ValueError('Fontes fora do contrato')
    source_hash=sha256(bronze/'_bronze.json')
    identity={'scope':'expansion_silver_v1','bronze_manifest_sha256':source_hash,
        'bronze_selection_id':approved['selection_id'],'contract_sha256':sha256(contract_path),
        'spark_version':spark.version,'implementation':{p.name:sha256(p) for p in
        [Path(__file__),Path(__file__).with_name('quality.py'),Path(__file__).with_name('storage.py')]}}
    identifier=digest(identity)[:24]
    namespace=repo/'data/silver/expansion';namespace.mkdir(parents=True,exist_ok=True)
    dest=namespace/identifier
    with _ingestion_lock(namespace):
        if dest.exists():return verify_package(dest,'_silver.json',identity),True
        stage=namespace/'.staging'/uuid.uuid4().hex;stage.mkdir(parents=True)
        started=time.monotonic()
        manifest={'id':identifier,'identity':identity,'identity_sha256':digest(identity),'status':'running',
            'tables':{},'validation':{},'population':approved['population'],
            'dependency_rule':'changed_case_id_in_any_source_then_old_and_new_months',
            'events':'simulated_full_row_upserts_only_no_source_CDC'}
        base=spark.read.parquet(str(bronze/'tables/train_base')).select('case_id').cache()
        try:
            order=['train_base']+[n for n in spec['tables'] if n!='train_base']
            for name in order:
                begin=time.monotonic();rule=spec['tables'][name]
                source=spark.read.parquet(str(bronze/'tables'/name))
                expected=transform(source,rule)
                quality=validate_silver(expected,rule,None if name=='train_base' else base)
                if rule['required_base_coverage'] and base.join(expected.select('case_id'),'case_id','left_anti').count():
                    raise ValueError('Cobertura obrigatória incompleta')
                target=stage/'tables'/name
                expected.write.format('delta').mode('errorifexists').save(str(target))
                actual=spark.read.format('delta').load(str(target))
                readback=key_audit(actual,rule['key'])
                proof=compare_keyed(expected,actual,rule['key'])
                if not proof['success'] or readback['rows']!=quality['rows']:
                    raise ValueError('Reconciliação Silver falhou')
                group_audit=None
                if rule['group_parent']:
                    parent=spark.read.parquet(str(bronze/'tables'/rule['group_parent'])).select('case_id','num_group1').distinct()
                    orphans=actual.select('case_id','num_group1').distinct().join(parent,['case_id','num_group1'],'left_anti').count()
                    group_audit={'unmatched_groups':orphans,'rule':'audit_only_no_assumed_cross_table_join'}
                entry=pin_delta(spark,target,str((dest/'tables'/name).relative_to(repo)),readback['rows'])
                manifest['tables'][name]=entry
                manifest['validation'][name]={'quality':quality,'readback':readback,'preservation':proof,
                    'date_new_nulls':0,'rejected_rows':0,'group_parent':group_audit,
                    'duration_seconds':round(time.monotonic()-begin,3)}
                atomic_json(stage/'_progress.json',manifest)
                print(f'Silver {name}: {readback["rows"]} registros, chaves e valores aprovados',flush=True)
                if name==fail_after_table:raise RuntimeError('Falha Silver privada injetada')
            if sha256(bronze/'_bronze.json')!=source_hash:raise ValueError('Manifesto Bronze mudou')
            verify_committed(bronze,original['identity'])
            manifest['duration_seconds']=round(time.monotonic()-started,3)
            return finish_package(stage,dest,manifest,'_silver.json'),False
        except BaseException as exc:
            manifest.update(status='failed',error_type=type(exc).__name__)
            atomic_json(stage/'_progress.json',manifest)
            raise
        finally:base.unpersist()


def open_silver(repo,spark,path):
    manifest=verify_package(path,'_silver.json')
    ancestor=manifest
    seen={manifest['id']}
    while ancestor.get('parent_id'):
        parent_path=path.parent/ancestor['parent_id']
        if ancestor['parent_id'] in seen or sha256(parent_path/'_silver.json')!=ancestor['identity']['parent_manifest_sha256']:
            raise ValueError('Cadeia Silver inválida ou pai alterado')
        ancestor=verify_package(parent_path,'_silver.json')
        seen.add(ancestor['id'])
    return manifest,{n:open_pin(repo,spark,t) for n,t in manifest['tables'].items()}
