"""Matriz local F09.6: entradas reais aprovadas; falhas injetadas em destinos privados."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import json
from unittest.mock import patch
from src.operation.runner import supervise
from src.object_store.fixtures import temporary_objects
from src.object_store.client import ObjectClient
from src.object_store.service import ObjectService
from src.object_store.publication import current,verify_publication
from src.object_store.spark import create_object_spark
from src.pipelines.download_home_credit import sha256
from src.pipelines import run_lakehouse as pipeline

repo=Path.cwd();out=repo/'artifacts/f09/validation/f096';service=ObjectService(repo)
sample='7d58bbdaa00cbabfbce54d26';source='artifacts/f04/runs/20261113T020347Z_1609747b.json'
real=ObjectClient(repo);preexisting=service.status()['status']=='running';service.start()
real_keys=[real.config['prefix']+'/publications/'+sample+'/_CURRENT.json',real.config['prefix']+'/operational-publications/'+sample+'/_CURRENT.json']
protected={key:real.get(key)[0] for key in real_keys}
service.stop()
original_publish=pipeline._publish;results={};expected_pointer=None;outage_observed=[]
fixture=temporary_objects(repo);client=fixture.__enter__();fixture_prefix=client.config['prefix']
registry=fixture_prefix+'/operational-publications/'+sample
scenario='success';outage_fired=False

def publisher(ctx,client_arg,registry_arg,spark,source_frames,plan,counts,spec,identity,fingerprints,references,parent=None,hook=None):
    global outage_fired
    assert registry_arg==registry and client_arg is client
    frames=source_frames
    if scenario=='schema_invalid':
        from pyspark.sql import functions as F
        frames={**frames,'credit_cases':frames['credit_cases'].withColumn('unapproved_column',F.lit(1))}
    if scenario=='quality_rejected':
        from pyspark.sql import functions as F
        frames={**frames,'credit_cases':frames['credit_cases'].withColumn('target',F.lit(7).cast('long'))}
    def fault(stage):
        global outage_fired
        if scenario=='service_unavailable' and not outage_fired and stage=='after_commit:gold.abt:create':
            outage_fired=True;service.stop()
            # Falha real do SDK, após o commit privado: nenhum validador é substituído.
            client.get(registry+'/_CURRENT.json')
            raise AssertionError('Endpoint continuou disponível')
    return original_publish(ctx,client_arg,registry_arg,spark,frames,plan,counts,spec,identity,
        fingerprints,references,parent=parent,hook=fault)


def before_retry(delay):
    service.start()
    try:
        assert client.get(registry+'/_CURRENT.json')[0]==expected_pointer
        outage_observed.append({'current_preserved_before_retry':True})
    finally:service.stop()

try:
    with patch.object(pipeline,'ObjectClient',lambda _:client),patch.object(pipeline,'_publish',publisher):
        for name in ('success','source_missing','schema_invalid','quality_rejected','service_unavailable'):
            scenario=name
            (out/'progress.json').write_text(json.dumps({'stage':name,'status':'running'}))
            options={'sample':sample,'source_report':source,'mode':'rebuild','batch':'b00_w000_051'}
            if name=='source_missing':
                missing=out/'intentionally_absent.json';assert not missing.exists()
                options['source_report']=missing.relative_to(repo).as_posix()
            result=supervise(repo,options,max_attempts=2,retry_delay=0,sleep=before_retry,
                reports_directory=out/'operations')
            operation=json.loads(Path(result['report']).read_text())
            assert result['exit_code']==(3 if name in ('source_missing','schema_invalid','quality_rejected') else 0),name
            assert len(operation['attempts'])==(2 if name=='service_unavailable' else 1)
            runs=[]
            for attempt in operation['attempts']:
                reference=attempt['run_report'];assert sha256(repo/reference['path'])==reference['sha256']
                runs.append(json.loads((repo/reference['path']).read_text()))
                assert not attempt['cleanup_errors']
            if name in ('source_missing','schema_invalid','quality_rejected'):
                assert not operation['attempts'][0]['retryable']
                assert operation['stage']==('inputs' if name=='source_missing' else 'publication')
            if name=='quality_rejected':
                assert operation['attempts'][0]['category']=='quality_rejected'
                assert runs[0]['quality_failure']['status']=='failed'
            service.start()
            try:
                observed=client.get(registry+'/_CURRENT.json')[0]
                if name in ('source_missing','schema_invalid','quality_rejected'):assert observed==expected_pointer,name
                else:expected_pointer=observed
                if name=='service_unavailable':
                    assert outage_fired and len(outage_observed)==1
                    assert operation['attempts'][0]['error_type']=='EndpointConnectionError'
                    assert runs[0]['state_prefix']==runs[1]['state_prefix']
                    assert runs[0]['batches'][0]['versions_after']==runs[1]['batches'][0]['versions_after']
                    assert all(m['inserts']==m['updates']==0 for m in runs[1]['batches'][0]['metrics'].values())
                results[name]={'operation':result,'attempts':len(operation['attempts']),
                    'stage':operation['stage'],'current_publication':json.loads(observed)['publication_id'],
                    'run_ids':[a['run_id'] for a in operation['attempts']],
                    'counts':runs[-1].get('counts'),'failure_preserves_current':name not in ('success','service_unavailable')}
            finally:service.stop()
            (out/'progress.json').write_text(json.dumps({'stage':name,'status':'passed'}))
    # Consumir a publicação recuperada com um novo Spark, sem patches de validadores.
    service.start();spark=create_object_spark(repo,app_name='f096-final-reader')
    try:
        manifest,frames=verify_publication(client,registry,json.loads(expected_pointer)['publication_id'],spark)
        assert frames['gold.abt'].count()==35045 and frames['gold.monthly_metrics'].count()==12
        assert manifest['tables']['gold.abt']['version']==0
        final_tables=manifest['tables']
    finally:spark.stop()
finally:
    service.start()
    try:
        fixture.__exit__(None,None,None)
        assert not client.list(fixture_prefix+'/')
        for key,value in protected.items():assert real.get(key)[0]==value
    finally:
        if not preexisting:service.stop()
result={'status':'passed','fixture_prefix':fixture_prefix,'fixture_objects_removed':True,
    'real_current_pointers_preserved':True,'source':'approved Home Credit cohort; no source data mutated',
    'injection':'SDK destination factory and producer-output/failure hooks only; actual validators, Spark, Delta, S3 and supervisor',
    'harness_sha256':sha256(Path(__file__)),'cases':results,'outage_proofs':outage_observed,
    'final_tables':final_tables,'supervisor_sha256':sha256(repo/'src/operation/runner.py'),
    'executor_sha256':sha256(repo/'src/pipelines/run_lakehouse.py')}
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'progress.json').write_text(json.dumps({'status':'passed','stage':'complete'}))
print(json.dumps({'status':'passed','cases':results,'fixture_removed':True}))
