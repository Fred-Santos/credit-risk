"""E07: espelho Delta imutável por bytes, aprovação conjunta e CURRENT por CAS."""
import hashlib
import json
from pathlib import Path,PurePosixPath
from urllib.parse import unquote
import re
import uuid
from src.bronze.build_bronze import _ingestion_lock
from src.expansion.analysis import verify_analysis
from src.expansion.storage import verify_package,safe_path
from src.expansion.silver import load_contract
from src.object_store.client import ObjectClient
from src.object_store.config import local_path
from src.object_store.publication import current,_activate,verify_publication
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import NoPublicationError,atomic_json
from src.quality.event_contracts import digest
from src.silver.initial_delta import _files

PREFIX='lakehouse-expansion-v1'
ANALYSIS_KEYS={'monthly':['MONTH'],'coverage':['MONTH','source_table'],'missingness':['MONTH','feature'],
               'composition':['MONTH','dimension','category'],'period_compare':['period']}


def expansion_client(repo):
    client=ObjectClient(repo);client.config={**client.config,'prefix':PREFIX}
    return client


def registry(client,selection_id):
    if not re.fullmatch('[0-9a-f]{24}',selection_id):raise ValueError('Seleção inválida')
    return client.config['prefix']+'/publications/'+selection_id


def source_set(repo,silver_path,gold_path,analysis_path):
    silver=verify_package(silver_path,'_silver.json');gold=verify_package(gold_path,'_gold.json');analysis=verify_analysis(analysis_path)
    if (gold['identity']['silver_manifest_sha256']!=sha256(silver_path/'_silver.json')
            or gold['dependencies']!=silver['tables']
            or analysis['identity']['gold_manifest_sha256']!=sha256(gold_path/'_gold.json')
            or analysis['identity']['silver_manifest_sha256']!=sha256(silver_path/'_silver.json')
            or gold['case_intersection']!=0 or gold['ml_ready'] or gold['eligible_predictors']):
        raise ValueError('Cadeia Silver/Gold/análise inconsistente ou alegação ML indevida')
    contract=load_contract(repo/'configs/contracts/expansion_silver_v1.yaml')
    if set(contract['tables'])!=set(silver['tables']) or set(gold['blocks'])!=set(silver['tables'])-{'train_base'}:
        raise ValueError('Conjunto de fontes incompleto')
    entries={}
    for name,pin in silver['tables'].items():entries['silver.'+name]=(pin,contract['tables'][name]['key'])
    for name,pin in gold['blocks'].items():entries['gold.block_'+name]=(pin,['case_id'])
    if set(gold['products'])!={'development','evaluation'}:raise ValueError('Populações incompletas')
    for population,product in gold['products'].items():
        for kind in ('features','labels'):entries['gold.'+population+'_'+kind]=(product[kind],['case_id'])
    if set(analysis['tables'])!=set(ANALYSIS_KEYS):raise ValueError('Produtos analíticos incompletos')
    for name,pin in analysis['tables'].items():entries['gold.analysis_'+name]=(pin,ANALYSIS_KEYS[name])
    approved_roots=[silver_path,gold_path,analysis_path]
    references={str((path/name).relative_to(repo)):sha256(path/name) for path,name in
        [(silver_path,'_silver.json'),(gold_path,'_gold.json'),(analysis_path,'_analysis.json')]}
    for name,expected in analysis['report_files'].items():references[str((analysis_path/'report'/name).relative_to(repo))]=expected
    for relative in ['configs/contracts/expansion_silver_v1.yaml','configs/contracts/expansion_gold_v1.yaml',
                     'configs/contracts/expansion_feature_sources_v1.yaml','configs/expansion_features_v1.yaml',
                     'configs/temporal_policy_v1.yaml','configs/expansion_analysis_v1.yaml']:
        path=repo/relative
        if path.exists():references[relative]=sha256(path)
    ancestor=silver;seen={ancestor['id']}
    while ancestor.get('parent_id'):
        parent_id=ancestor['parent_id']
        if not re.fullmatch('[0-9a-f]{24}',parent_id) or parent_id in seen:raise ValueError('Cadeia Silver inválida')
        parent_path=silver_path.parent/parent_id
        if sha256(parent_path/'_silver.json')!=ancestor['identity']['parent_manifest_sha256']:raise ValueError('Pai Silver alterado')
        ancestor=verify_package(parent_path,'_silver.json');seen.add(parent_id);approved_roots.append(parent_path)
        references[str((parent_path/'_silver.json').relative_to(repo))]=sha256(parent_path/'_silver.json')
    sources={}
    for logical,(pin,key) in entries.items():
        path=safe_path(repo,pin['path'])
        if not any(path.is_relative_to(root.resolve()) for root in approved_roots):raise ValueError('Pin fora da cadeia aprovada')
        files=_files(path)
        if not files:raise ValueError('Delta sem arquivos/logs')
        relative_delta_actions(path,files)
        sources[logical]={'pin':pin,'key_columns':key,'files':files}
    selection=ancestor['identity']['bronze_selection_id']
    bronze=repo/'data/bronze/expansion'/selection/'_bronze.json'
    real_scope=gold['identity']['scope']=='expansion_temporal_abts_v1'
    if real_scope and not bronze.exists():raise ValueError('Manifesto Bronze ausente')
    if bronze.exists():
        if sha256(bronze)!=ancestor['identity']['bronze_manifest_sha256']:raise ValueError('Lineage Bronze divergente')
        references[str(bronze.relative_to(repo))]=sha256(bronze)
    audit=repo/'artifacts/expansion/temporal'/(silver['id']+'.json')
    if real_scope and not {'monthly.png','monthly.svg','coverage.png','coverage.svg'}<=set(analysis['report_files']):raise ValueError('Gráficos obrigatórios ausentes')
    if real_scope and not audit.exists():raise ValueError('Auditoria temporal ausente')
    if audit.exists():
        if sha256(audit)!=gold['identity']['temporal_audit_sha256']:raise ValueError('Auditoria temporal divergente')
        references[str(audit.relative_to(repo))]=sha256(audit)
    for path,expected in [(repo/'configs/contracts/expansion_silver_v1.yaml',silver['identity'].get('contract_sha256')),
                          (repo/'configs/contracts/expansion_gold_v1.yaml',gold['identity'].get('gold_contract_sha256')),
                          (repo/'configs/expansion_analysis_v1.yaml',analysis['identity']['policy_sha256'])]:
        if expected is not None and sha256(path)!=expected:raise ValueError('Contrato/política atual diverge da aprovação')
    return {'silver':silver,'gold':gold,'analysis':analysis,'sources':sources,'references':references,'selection_id':selection}


def relative_delta_actions(path,files):
    for name in files:
        if not re.fullmatch(r'_delta_log/\d{20}\.json',name):continue
        for line in (path/name).open():
            action=json.loads(line)
            for kind in ('add','remove'):
                if kind not in action:continue
                value=unquote(action[kind]['path']);relative=PurePosixPath(value)
                if relative.is_absolute() or '..' in relative.parts or ':' in value or value not in files:
                    raise ValueError('Log Delta referencia caminho externo ou arquivo não pinado')


def put_file_once(client,key,path,expected):
    """Upload em streaming; uma divergência nunca autoriza sobrescrita."""
    if sha256(path)!=expected:raise ValueError('Origem alterada antes do upload')
    if not client.exists(key):
        from botocore.exceptions import ClientError
        try:
            with path.open('rb') as handle:client.s3.put_object(Bucket=client.bucket,Key=key,Body=handle,IfNoneMatch='*')
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode']!=412:raise
    if client.checksum(key)!=expected or sha256(path)!=expected:raise ValueError('Cópia/objeto divergente; preservar para diagnóstico')


def approve_and_activate(repo,client,spark,manifest,registry_key,run_id,hook):
    # Leitura independente pela mesma API usada por consumidores, antes de ativar.
    verify_publication(client,registry_key,manifest['publication_id'],spark)
    hook('before_pointer')
    activation=_activate(client,registry_key,manifest,run_id)
    hook('after_pointer')
    return activation


def publish(repo,client,spark,silver_path,gold_path,analysis_path,*,hook=None,allow_simulated=False):
    hook=hook or (lambda stage:None)
    bundle=source_set(repo,silver_path,gold_path,analysis_path)
    if bundle['gold']['identity']['scope']!='expansion_temporal_abts_v1' and not client.config['prefix'].startswith('fixtures/'):
        raise ValueError('Fonte inventada só é permitida em prefixo de fixture')
    if bundle['silver'].get('is_simulated') and not allow_simulated:raise ValueError('Publicação simulada exige opt-in explícito')
    identity={'scope':'expansion_analytics_v1','is_simulated':bool(bundle['silver'].get('is_simulated',False)),'selection_id':bundle['selection_id'],
        'silver_id':bundle['silver']['id'],'gold_id':bundle['gold']['id'],'analysis_id':bundle['analysis']['id'],
        'source_references':bundle['references'],
        'sources':{name:{'uuid':v['pin']['delta_table_id'],'version':v['pin']['version'],'files':v['files']} for name,v in bundle['sources'].items()},
        'publication_implementation_sha256':sha256(Path(__file__))}
    identifier=digest(identity)[:24];reg=registry(client,bundle['selection_id']);run_id=uuid.uuid4().hex
    record={'run_id':run_id,'publication_id':identifier,'registry':reg,'status':'running'}
    control=local_path(repo,client.config['control_directory']);control.mkdir(parents=True,exist_ok=True)
    try:
        with _ingestion_lock(control,'.writer.lock'):
            client.ensure_bucket()
            manifest_key=reg+'/manifests/'+identifier+'.json'
            if client.exists(manifest_key):
                manifest=client.json(manifest_key)
                if manifest['identity']!=identity:raise ValueError('Identidade do manifesto divergente')
                record['reused']=True
            else:
                prefix=client.config['prefix']+'/published/'+bundle['selection_id']+'/'+identifier
                intent_key=reg+'/intents/'+identifier+'.json'
                if not client.exists(intent_key):
                    if client.list(prefix+'/'):raise ValueError('Prefixo ocupado sem intenção; não sobrescrever')
                    client.put_json(intent_key,{'identity':identity,'token':uuid.uuid4().hex})
                if client.json(intent_key)['identity']!=identity:raise ValueError('Intenção incompatível')
                references=[]
                for relative,expected in bundle['references'].items():
                    key=reg+'/blobs/'+expected
                    put_file_once(client,key,safe_path(repo,relative),expected)
                    references.append({'key':key,'sha256':expected,'local_source':relative})
                tables={}
                for logical,source in bundle['sources'].items():
                    layer,name=logical.split('.',1);pin=source['pin'];key=prefix+'/'+layer+'/'+name
                    expected_keys={key+'/'+relative for relative in source['files']}
                    if set(client.list(key+'/'))-expected_keys:raise ValueError('Objetos extras no prefixo privado')
                    for relative,expected in source['files'].items():
                        put_file_once(client,key+'/'+relative,safe_path(repo,pin['path'])/relative,expected)
                    tables[logical]={'key':key,'uri':client.uri(key),'delta_table_id':pin['delta_table_id'],
                        'version':pin['version'],'schema':pin['schema'],'rows':pin['rows'],
                        'key_columns':source['key_columns'],'files':source['files'],
                        'source':{'path':pin['path'],'uuid':pin['delta_table_id'],'version':pin['version']}}
                    hook('after_copy:'+logical)
                    print('Espelho S3 conferido:',logical,flush=True)
                manifest={'format_version':1,'status':'passed','publication_id':identifier,'identity':identity,
                    'tables':tables,'validations':{'source_closure':{'status':'passed'},'byte_equivalence':{'status':'passed'}},
                    'provenance':{},'references':references,
                    'details':{'ml_ready':False,'eligible_predictors':[],
                        'lineage':'unchanged_delta_bytes_uuid_versions_pinned_to_approved_local_manifests',
                        'labels':'separate_paths_explicit_opt_in','table_count':len(tables)},
                    'retention':{'days':30,'pins':'indefinite','real_vacuum':'forbidden',
                        'delta_log_properties':'preserved_from_source','enforcement':'immutable_prefix_no_destructive_maintenance'}}
                # Conferir dados S3 reais antes de publicar o manifesto de aprovação.
                verify_candidate(client,spark,manifest)
                hook('before_manifest')
                client.put_json(manifest_key,manifest)
                record['reused']=False
            activation=approve_and_activate(repo,client,spark,manifest,reg,run_id,hook)
            record.update(status='passed',activation=activation,tables=len(manifest['tables']),
                object_bytes=sum(client.list(client.config['prefix']+'/published/'+bundle['selection_id']+'/'+identifier+'/').values()))
    except BaseException as error:
        record.update(status='failed',error_type=type(error).__name__)
        try:record['current_after_failure']=current(client,reg)[0]['publication_id']
        except NoPublicationError:record['current_after_failure']=None
        except Exception as lookup_error:record.update(current_after_failure='unknown',current_lookup_error=type(lookup_error).__name__)
        atomic_json(repo/'artifacts/expansion/publication_attempts'/(run_id+'.json'),record)
        raise
    atomic_json(repo/'artifacts/expansion/publication_attempts'/(run_id+'.json'),record)
    return manifest,record


def verify_candidate(client,spark,manifest):
    from delta.tables import DeltaTable
    for name,entry in manifest['tables'].items():
        if client.inventory(entry['key'])!=entry['files']:raise ValueError('S3 diverge dos bytes aprovados')
        table=DeltaTable.forPath(spark,entry['uri'])
        if (table.detail().select('id').first()[0]!=entry['delta_table_id']
                or int(table.history(1).first().version)!=entry['version']):raise ValueError('UUID/versão S3 divergentes')
        frame=spark.read.format('delta').option('versionAsOf',entry['version']).load(entry['uri'])
        if dict(frame.dtypes)!=entry['schema'] or frame.count()!=entry['rows']:raise ValueError('Readback S3 divergente')
    for ref in manifest['references']:
        if client.checksum(ref['key'])!=ref['sha256']:raise ValueError('Referência S3 divergente')


def consume(client,spark,selection_id,publication_id=None,*,include_evaluation_labels=False):
    reg=registry(client,selection_id)
    chosen=current(client,reg)[0]['publication_id'] if publication_id is None else publication_id
    manifest,frames=verify_publication(client,reg,chosen,spark)
    # A guarda é de API; o proprietário do armazenamento ainda pode ler diretamente.
    if not include_evaluation_labels:
        frames.pop('gold.evaluation_labels',None)
        if 'silver.train_base' in frames:frames['silver.train_base']=frames['silver.train_base'].drop('target')
    return manifest,frames
