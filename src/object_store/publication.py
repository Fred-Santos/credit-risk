"""Intenção/manifesto/CURRENT pela API S3, sob um escritor cooperante do host.

Não usa rename, mkdir ou flock em URIs de dados. A exclusão do driver é controle
local explícito; não autoriza vários hosts/JVMs escrevendo as tabelas S3.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import re
import uuid

from src.bronze.build_bronze import _ingestion_lock
from src.object_store.config import local_path,s3_key
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import NoPublicationError,atomic_json
from src.quality.contracts import check_schema
from src.quality.event_contracts import digest
from src.silver.incremental import _commit_metadata,_restore_conf


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{24}',value):raise ValueError('publication_id inválido')
    return value


def registry_key(client,selection):
    identifier(selection)
    return client.config['prefix']+'/publications/'+selection


def current(client,registry):
    from botocore.exceptions import ClientError
    try:data,etag=client.get(registry+'/_CURRENT.json')
    except ClientError as error:
        if error.response['ResponseMetadata']['HTTPStatusCode']==404:raise NoPublicationError('Nenhuma publicação aprovada em objetos')
        raise
    value=json.loads(data);identifier(value['publication_id'])
    manifest,_=client.get(registry+'/manifests/'+value['publication_id']+'.json')
    if hashlib.sha256(manifest).hexdigest()!=value['manifest_sha256']:
        raise ValueError('CURRENT S3 não corresponde ao manifesto')
    return value,etag


def verify_publication(client,registry,publication_id,spark):
    from delta.tables import DeltaTable
    publication_id=identifier(publication_id)
    manifest=client.json(registry+'/manifests/'+publication_id+'.json')
    if (manifest.get('status')!='passed' or manifest.get('format_version')!=1
        or manifest.get('publication_id')!=publication_id or digest(manifest['identity'])[:24]!=publication_id
        or not manifest.get('validations') or any(v.get('status')!='passed' for v in manifest['validations'].values())):
        raise ValueError('Manifesto S3 não aprovado')
    for entry in manifest['provenance'].values():
        if client.checksum(entry['key'])!=entry['sha256']:raise ValueError('Proveniência S3 alterada')
    for entry in manifest.get('references',[]):
        if client.checksum(entry['key'])!=entry['sha256']:raise ValueError('Referência S3 alterada')
    frames={}
    for name,entry in manifest['tables'].items():
        key=s3_key(entry['key'])
        expected_prefix=client.config['prefix']+'/published/'+manifest['identity']['selection_id']+'/'+publication_id+'/'
        if not key.startswith(expected_prefix) or entry['uri']!=client.uri(key):raise ValueError('Tabela S3 fora da publicação')
        if client.inventory(key)!=entry['files']:raise ValueError('Arquivos/logs S3 publicados mudaram')
        delta=DeltaTable.forPath(spark,entry['uri'])
        if delta.detail().select('id').first()[0]!=entry['delta_table_id'] or int(delta.history(1).first().version)!=entry['version']:
            raise ValueError('UUID/versão Delta S3 mudou')
        frame=spark.read.format('delta').option('versionAsOf',entry['version']).load(entry['uri'])
        check_schema(frame,{'schema':entry['schema']})
        if frame.count()!=entry['rows']:raise ValueError('Contagem S3 publicada mudou')
        frames[name]=frame
    return manifest,frames


def _activate(client,registry,manifest,run_id):
    publication_id=manifest['publication_id']
    manifest_data,_=client.get(registry+'/manifests/'+publication_id+'.json')
    try:previous,etag=current(client,registry)
    except NoPublicationError:previous,etag=None,None
    if previous and previous['publication_id']==publication_id:
        return {'publication_id':publication_id,'reused':True}
    value={'format_version':1,'publication_id':publication_id,'manifest_sha256':hashlib.sha256(manifest_data).hexdigest(),
           'run_id':run_id,'activated_at_utc':datetime.now(timezone.utc).isoformat()}
    client.put_json(registry+'/activations/'+run_id+'_'+uuid.uuid4().hex[:8]+'.json',value)
    client.replace(registry+'/_CURRENT.json',json.dumps(value,sort_keys=True).encode(),etag)
    return {'publication_id':publication_id,'reused':False}


@contextmanager
def open_object_publication(client,registry,spark,publication_id=None):
    chosen=current(client,registry)[0]['publication_id'] if publication_id is None else publication_id
    manifest,frames=verify_publication(client,registry,chosen,spark)
    key=registry+'/manifests/'+chosen+'.json';before=client.checksum(key)
    yield manifest,frames
    if client.checksum(key)!=before:raise RuntimeError('Manifesto S3 mudou durante consumo')
    for entry in manifest['tables'].values():
        if client.inventory(entry['key'])!=entry['files']:raise RuntimeError('Tabela S3 mudou durante consumo')


def activate_object_publication(ctx,client,registry,spark,publication_id):
    control=local_path(ctx.repo_root,client.config['control_directory'])
    with _ingestion_lock(control,'.writer.lock'):
        manifest,_=verify_publication(client,registry,publication_id,spark)
        return _activate(client,registry,manifest,ctx.run_id)


class ObjectTransaction:
    def __init__(self,ctx,client,registry,spark,identity,fingerprints,hook=None):
        self.ctx,self.client,self.registry,self.spark,self.identity=ctx,client,registry,spark,identity
        self.id=digest(identity)[:24];self.hook=hook or (lambda stage:None)
        self.intent_key=registry+'/intents/'+self.id+'.json'
        self.provenance={}
        for name,expected in fingerprints.items():
            path=ctx.repo_root/name
            if sha256(path)!=expected:raise ValueError('Proveniência mudou')
            key=registry+'/blobs/'+expected;client.put_new(key,path.read_bytes())
            self.provenance[name]={'key':key,'sha256':expected}
        if not client.exists(self.intent_key):
            client.put_json(self.intent_key,{'publication_id':self.id,'identity':identity,'token':uuid.uuid4().hex})
        self.intent=client.json(self.intent_key)
        if self.intent['identity']!=identity:raise ValueError('Intento S3 incompatível')
        self.entries,self.validations,self.details={},{},{}

    def table_key(self,layer,name):
        if layer not in ('silver','gold') or not re.fullmatch('[a-z][a-z0-9_]+',name):raise ValueError('Camada/tabela inválida')
        return self.client.config['prefix']+'/published/'+self.identity['selection_id']+'/'+self.id+'/'+layer+'/'+name

    def table_path(self,layer,name):return self.client.uri(self.table_key(layer,name))

    def metadata(self,key,stage):
        return {'scope':'object_publication_v1','publication_id':self.id,'token':self.intent['token'],'table':key,'stage':stage}

    @contextmanager
    def commit(self,key,stage):
        self.hook('before_commit:'+key+':'+stage)
        name,prior=_commit_metadata(self.spark,self.metadata(key,stage))
        try:yield
        finally:_restore_conf(self.spark,name,prior)
        self.hook('after_commit:'+key+':'+stage)

    def verify_owned(self,path,key):
        from delta.tables import DeltaTable
        table=DeltaTable.forPath(self.spark,str(path))
        for row in table.history().select('userMetadata').collect():
            value=json.loads(row.userMetadata or '{}')
            if value!=self.metadata(key,value.get('stage','')):raise ValueError('Commit S3 não pertence ao intento')
        return table

    def create_table(self,layer,name,initial):
        from delta.tables import DeltaTable
        key=self.table_key(layer,name);uri=self.client.uri(key);logical=layer+'.'+name
        owner_key=self.registry+'/owners/'+self.id+'/'+logical+'.json'
        owner={'token':self.intent['token'],'key':key}
        existing=self.client.list(key+'/')
        if existing and not self.client.exists(owner_key):raise ValueError('Prefixo existente sem proprietário; preservar objetos')
        self.client.put_json(owner_key,owner)
        if existing:
            if DeltaTable.isDeltaTable(self.spark,uri):return self.verify_owned(uri,logical)
            if any(re.fullmatch(r'\d{20}\.json',p.rsplit('/',1)[-1]) for p in existing):
                raise ValueError('Commit S3 existente não pode ser removido')
            # Resíduos privados sem commit; nunca dados de publicação aprovada.
            if self.client.exists(self.registry+'/manifests/'+self.id+'.json'):raise ValueError('Publicação aprovada é imutável')
            for object_key in existing:self.client.s3.delete_object(Bucket=self.client.bucket,Key=object_key)
        with self.commit(logical,'create'):
            (initial.write.format('delta').mode('errorifexists')
             .option('delta.logRetentionDuration','interval 30 days')
             .option('delta.deletedFileRetentionDuration','interval 30 days').save(uri))
        return DeltaTable.forPath(self.spark,uri)

    def record_table(self,layer,name,schema,key):
        table_key=self.table_key(layer,name);uri=self.client.uri(table_key)
        table=self.verify_owned(uri,layer+'.'+name);detail=table.detail().select('id','properties').first()
        if any(detail.properties.get(n)!='interval 30 days' for n in
            ('delta.logRetentionDuration','delta.deletedFileRetentionDuration')):raise ValueError('Retenção S3 incompatível')
        version=int(table.history(1).first().version)
        frame=self.spark.read.format('delta').option('versionAsOf',version).load(uri)
        check_schema(frame,{'schema':schema})
        self.entries[layer+'.'+name]={'key':table_key,'uri':uri,'delta_table_id':detail.id,'version':version,
            'schema':schema,'key_columns':key,'rows':frame.count(),'files':self.client.inventory(table_key)}
        return frame

    def publish(self):
        if not self.entries or not self.validations or any(v.get('status')!='passed' for v in self.validations.values()):
            raise ValueError('Manifesto S3 exige validações aprovadas')
        manifest={'format_version':1,'status':'passed','publication_id':self.id,'identity':self.identity,
            'tables':self.entries,'validations':self.validations,'details':self.details,'provenance':self.provenance,
            'references':self.details.pop('references',[]),'retention':{'days':30,'pins':'indefinite','real_vacuum':'forbidden'}}
        self.hook('before_manifest')
        self.client.put_json(self.registry+'/manifests/'+self.id+'.json',manifest)
        self.hook('before_pointer')
        activation=_activate(self.client,self.registry,manifest,self.ctx.run_id)
        self.hook('after_pointer')
        return manifest,activation


def publish_object_snapshot(ctx,client,registry,spark,identity,fingerprints,builder,hook=None):
    control=local_path(ctx.repo_root,client.config['control_directory'])
    report={'run_id':ctx.run_id,'publication_id':digest(identity)[:24],'status':'running'}
    try:
        with _ingestion_lock(control,'.writer.lock'):
            client.ensure_bucket()  # Falha rápida quando serviço/autenticação estão indisponíveis.
            key=registry+'/manifests/'+report['publication_id']+'.json'
            if client.exists(key):
                manifest,_=verify_publication(client,registry,report['publication_id'],spark)
                if manifest['identity']!=identity:raise ValueError('Manifesto S3 tem outra identidade')
                report['reused']=True
                activation=_activate(client,registry,manifest,ctx.run_id)
            else:
                tx=ObjectTransaction(ctx,client,registry,spark,identity,fingerprints,hook=hook)
                builder(tx)
                if any(sha256(ctx.repo_root/p)!=h for p,h in fingerprints.items()):raise RuntimeError('Código/configuração mudou durante escrita S3')
                manifest,activation=tx.publish();report['reused']=False
            report.update(status='passed',activation=activation)
    except BaseException as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error))
        atomic_json(ctx.repo_root/'artifacts/f08/attempts'/(ctx.run_id+'.json'),report)
        raise
    atomic_json(ctx.repo_root/'artifacts/f08/attempts'/(ctx.run_id+'.json'),report)
    return manifest,report
