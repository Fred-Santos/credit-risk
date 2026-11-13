"""Replay F04 nativo em S3A; estado privado congelado antes de ser referência."""
import json
import re

from src.bronze.event_parquet import check_conflicts,revision_index
from src.quality.contracts import check_schema
from src.quality.event_contracts import digest
from src.quality.silver_contracts import validate_silver_frames
from src.silver.incremental import (EVENT_STATE,_commit_metadata,_restore_conf,_metrics,
    deduplicate,transform_candidates)
from src.silver.initial_delta import TABLES


class ObjectIncremental:
    def __init__(self,client,spark,prefix,identity,plan):
        self.client,self.spark,self.prefix,self.identity,self.plan=client,spark,prefix,identity,plan
        self.identity_sha=digest(identity)

    def path(self,name):return self.client.uri(self.prefix+'/'+name)

    def initialize(self):
        from delta.tables import DeltaTable
        from pyspark.sql.types import StructType,StructField,_parse_datatype_string
        key=self.prefix+'/_state.json'
        if self.client.exists(key):
            header=self.client.json(key)
            if header['identity']!=self.identity:raise ValueError('Estado S3 vinculado a outra identidade')
            self.verify();return
        marker_key=self.prefix+'/_intent.json'
        self.client.put_json(marker_key,{'identity':self.identity})
        tables={}
        for name,spec in self.plan['tables'].items():
            uri=self.path(name)
            existing=self.client.list(self.prefix+'/'+name+'/')
            if existing:
                if not DeltaTable.isDeltaTable(self.spark,uri):raise ValueError('Estado inicial S3 incompleto exige inspeção; preservar objetos')
                table=DeltaTable.forPath(self.spark,uri)
            else:
                schema=StructType([StructField(c,_parse_datatype_string(t),True) for c,t in {**spec['schema'],**EVENT_STATE}.items()])
                conf,prior=_commit_metadata(self.spark,{'scope':'object_incremental_v1','identity':self.identity_sha,'initialize':True})
                try:
                    (self.spark.createDataFrame([],schema).write.format('delta').mode('errorifexists')
                     .option('delta.logRetentionDuration','interval 30 days')
                     .option('delta.deletedFileRetentionDuration','interval 30 days').save(uri))
                finally:_restore_conf(self.spark,conf,prior)
                table=DeltaTable.forPath(self.spark,uri)
            for row in table.history().select('userMetadata').collect():
                meta=json.loads(row.userMetadata or '{}')
                if meta.get('identity')!=self.identity_sha:raise ValueError('Commit inicial S3 sem vínculo')
            tables[name]=table.detail().select('id').first()[0]
        self.client.put_json(key,{'identity':self.identity,'tables':tables})

    def verify(self):
        from delta.tables import DeltaTable
        header=self.client.json(self.prefix+'/_state.json')
        if header['identity']!=self.identity:raise ValueError('Cabeçalho incremental S3 incompatível')
        versions={}
        for name,spec in self.plan['tables'].items():
            delta=DeltaTable.forPath(self.spark,self.path(name))
            if delta.detail().select('id').first()[0]!=header['tables'][name]:raise ValueError('UUID incremental S3 mudou')
            check_schema(delta.toDF(),{'schema':{**spec['schema'],**EVENT_STATE}})
            for row in delta.history().select('userMetadata').collect():
                metadata=json.loads(row.userMetadata or '{}')
                if metadata.get('scope')!='object_incremental_v1' or metadata.get('identity')!=self.identity_sha:
                    raise ValueError('Commit externo no estado S3')
            versions[name]=int(delta.history(1).first().version)
        return versions

    def read(self,versions=None):
        result={}
        for name in self.plan['tables']:
            reader=self.spark.read.format('delta')
            if versions is not None:reader=reader.option('versionAsOf',versions[name])
            result[name]=reader.load(self.path(name))
        return result

    def apply(self,manifest,frames,indices,snapshot,policy,run_id,hook=None):
        from src.bronze.build_bronze import _ingestion_lock
        from src.object_store.config import local_path
        with _ingestion_lock(local_path(self.client.repo,self.client.config['control_directory']),'.writer.lock'):
            return self._apply(manifest,frames,indices,snapshot,policy,run_id,hook)

    def _apply(self,manifest,frames,indices,snapshot,policy,run_id,hook=None):
        from delta.tables import DeltaTable
        from pyspark import StorageLevel
        hook=hook or (lambda stage:None)
        if self.client.exists(self.prefix+'/_FROZEN.json'):raise ValueError('Estado S3 congelado não recebe novos commits')
        if manifest['binding']!=self.identity['source_binding'] or manifest['stream_id']!=self.identity['source_stream_id']:
            raise ValueError('Pacote não pertence ao stream de origem fixado')
        self.initialize();before=self.verify()
        check_conflicts(indices+[revision_index(f) for f in frames.values()])
        receipt_key=self.prefix+'/applied/'+manifest['batch_id']+'.json'
        if self.client.exists(receipt_key):
            receipt=self.client.json(receipt_key)
            if receipt['packet_sha256']!=manifest['packet_sha256']:raise ValueError('Pacote aplicado mudou de conteúdo')
        prepared,metrics={},{}
        try:
            for source in TABLES:
                chosen,dedup=deduplicate(frames[source],snapshot,source)
                treated,transformation=transform_candidates(chosen,snapshot,policy,source)
                prepared[source]=treated.persist(StorageLevel.MEMORY_AND_DISK)
                name=TABLES[source]
                action=_metrics(DeltaTable.forPath(self.spark,self.path(name)).toDF(),treated,snapshot['tables'][source]['key'])
                metrics[name]={**dedup,**action,'transformation':transformation}
            for source,frame in prepared.items():
                name=TABLES[source];stats=metrics[name]
                if stats['inserts']+stats['updates']==0:continue
                keys=snapshot['tables'][source]['key'];condition=' AND '.join(f't.`{c}`=s.`{c}`' for c in keys)
                hook('before_incremental_commit:'+name)
                conf,prior=_commit_metadata(self.spark,{'scope':'object_incremental_v1','identity':self.identity_sha,
                    'batch_id':manifest['batch_id'],'packet_sha256':manifest['packet_sha256'],'run_id':run_id})
                try:
                    (DeltaTable.forPath(self.spark,self.path(name)).alias('t').merge(frame.alias('s'),condition)
                     .whenMatchedUpdateAll(condition='s._source_revision > t._source_revision')
                     .whenNotMatchedInsertAll().execute())
                finally:_restore_conf(self.spark,conf,prior)
                hook('after_incremental_commit:'+name)
                actual=DeltaTable.forPath(self.spark,self.path(name)).history(1).first().operationMetrics
                if int(actual['numTargetRowsInserted'])!=stats['inserts'] or int(actual['numTargetRowsUpdated'])!=stats['updates']:
                    raise RuntimeError('Métricas MERGE S3 divergiram da classificação')
            validation=validate_silver_frames({n:f.select(*self.plan['tables'][n]['schema']) for n,f in self.read().items()},self.plan)
            after=self.verify()
            result={'status':'passed','batch_id':manifest['batch_id'],'packet_sha256':manifest['packet_sha256'],
                'versions_before':before,'versions_after':after,'metrics':metrics,'validation':validation}
            if not self.client.exists(receipt_key):self.client.put_json(receipt_key,result)
            return result
        finally:
            for frame in prepared.values():frame.unpersist()

    def freeze(self,snapshots,reconciliation):
        if reconciliation.get('status')!='passed':raise ValueError('Congelamento exige reconciliação aprovada')
        versions=self.verify()
        files={name:self.client.inventory(self.prefix+'/'+name) for name in self.plan['tables']}
        record={'status':'passed','identity':self.identity,'versions':versions,'snapshots':snapshots,
                'files':files,'reconciliation':reconciliation}
        self.client.put_json(self.prefix+'/_FROZEN.json',record)
        return record

    def verify_frozen(self):
        record=self.client.json(self.prefix+'/_FROZEN.json')
        if record['identity']!=self.identity or record['versions']!=self.verify():raise ValueError('Estado congelado S3 mudou')
        if any(self.client.inventory(self.prefix+'/'+name)!=files for name,files in record['files'].items()):
            raise ValueError('Arquivos do estado S3 congelado mudaram')
        return record
