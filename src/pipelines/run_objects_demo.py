"""F08: entradas espelhadas, replay S3A e publicação Silver+Gold em objetos."""
import argparse
from functools import reduce
from importlib.metadata import version
import json
from pathlib import Path
import time

from src.bronze.build_bronze import _ingestion_lock
from src.bronze.event_parquet import transport_schema,revision_index
from src.bronze.inputs import bind_sample
from src.gold.model import load_gold_contract
from src.gold.publish import prepare_gold
from src.object_store.client import ObjectClient
from src.object_store.config import local_path
from src.object_store.fixtures import capability_probe,lifecycle_fixture
from src.object_store.incremental import ObjectIncremental
from src.object_store.mirror import mirror_inputs,mirrored_directory,verify_mirror
from src.object_store.publication import (registry_key,current,verify_publication,open_object_publication,
    publish_object_snapshot,activate_object_publication)
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.pipelines.download_home_credit import sha256
from src.publication.evolution import prepare_silver,load_managed_contract
from src.publication.protocol import InjectedFailure,atomic_json,fail_at,local,verify_manifest
from src.publication.source import open_f04_snapshots,SNAPSHOTS
from src.quality.contracts import check_schema
from src.quality.event_contracts import digest
from src.quality.reconcile_bronze import compare_rows
from src.silver.incremental import reconstruct
from src.silver.initial_delta import TABLES
from src.silver.read_bronze import open_bronze_snapshot
from src.silver.transforms import load_silver_policy
from src.utils.run_context import RunContext

CODE=('src/pipelines/run_objects_demo.py','src/object_store/client.py','src/object_store/config.py',
      'src/object_store/service.py','src/object_store/spark.py','src/object_store/publication.py',
      'src/object_store/incremental.py','src/object_store/mirror.py','src/object_store/fixtures.py',
      'src/publication/evolution.py','src/publication/source.py','src/publication/protocol.py',
      'src/gold/model.py','src/gold/publish.py','src/gold/quality.py','src/silver/incremental.py',
      'src/silver/transforms.py','src/bronze/event_parquet.py','src/quality/contracts.py',
      'src/quality/reconcile_bronze.py','src/quality/silver_contracts.py','src/utils/spark.py',
      'src/utils/paths.py','src/utils/run_context.py','scripts/objects.sh','scripts/bootstrap_objects.sh',
      'scripts/install_object_store.py')
CONFIG=('configs/object_store_v1.yaml','configs/contracts/gold_v1.yaml','configs/contracts/silver_managed_v2.yaml',
        'configs/contracts/silver_initial_v1.yaml','configs/contracts/home_credit_v1.yaml',
        'configs/contracts/home_credit_events_v1.yaml','configs/silver_policy_v1.yaml',
        'configs/incremental_policy_v1.yaml','configs/spark.yaml','configs/paths.yaml',
        'configs/ivysettings.xml','requirements.lock','requirements.objects.lock','notebooks/analise_silver.ipynb')


def _runtime(repo,spark):
    names=('org.apache.hadoop_hadoop-aws-3.3.4.jar','com.amazonaws_aws-java-sdk-bundle-1.12.262.jar',
           'io.delta_delta-spark_2.12-3.3.2.jar','io.delta_delta-storage-3.3.2.jar')
    jars={name:sha256(repo/'.runtime/ivy/jars'/name) for name in names}
    return {'spark':spark.version,'delta':version('delta-spark'),'boto3':version('boto3'),
        'hadoop':spark.sparkContext._jvm.org.apache.hadoop.util.VersionInfo.getVersion(),
        'aws_java_sdk':spark.sparkContext._jvm.com.amazonaws.util.VersionInfoUtils.getVersion(),
        'jar_sha256':jars}


def _packets_from_objects(client,mirror,source,spark,snapshot):
    result=[]
    for record in source['generation']['publications']:
        batch=record['batch_id'];relative=source['events_root']+'/'+batch
        manifest=client.json(client.config['prefix']+'/inputs/'+mirror['mirror_id']+'/'+relative+'/_batch.json')
        if manifest!={k:v for k,v in record.items() if k!='reused'}:
            raise ValueError('Manifesto de lote S3 diverge da origem aprovada')
        frames={}
        for table in TABLES:
            frame=spark.read.parquet(mirrored_directory(client,mirror,relative+'/'+table))
            schema=transport_schema(snapshot,table)
            check_schema(frame,{'schema':{f.name:f.dataType.simpleString() for f in schema.fields}})
            if frame.count()!=manifest['counts'][table]:raise ValueError('Contagem do pacote S3 divergente')
            frames[table]=frame
        result.append((manifest,frames))
    return sorted(result,key=lambda pair:pair[0]['receipt_index'])


def replay_objects(ctx,client,spark,mirror,mirror_key,source,plan,snapshot,policy,fingerprints,runtime):
    identity={'selection_id':source['selection_id'],'source_binding':source['identity']['binding'],
        'source_stream_id':source['stream_id'],'mirror_key':mirror_key,'mirror_sha256':client.checksum(mirror_key),
        'code_and_configuration':fingerprints,'runtime':runtime}
    state_prefix=client.config['prefix']+'/working/'+source['selection_id']+'/'+digest(identity)[:24]
    state=ObjectIncremental(client,spark,state_prefix,identity,plan)
    if client.exists(state_prefix+'/_FROZEN.json'):
        return state,state.verify_frozen(),{'reused_frozen_state':True}
    packets=_packets_from_objects(client,mirror,source,spark,snapshot)
    histories={name:reduce(lambda a,b:a.unionByName(b),[frames[name] for _,frames in packets]) for name in TABLES}
    indices=[revision_index(frame) for frame in histories.values()]
    results=[];snapshots={}
    reverse={batch:label for label,batch in SNAPSHOTS.items()}
    for manifest,frames in packets:
        result=state.apply(manifest,frames,indices,snapshot,policy,ctx.run_id)
        results.append(result)
        original=client.json(state_prefix+'/applied/'+manifest['batch_id']+'.json')
        if manifest['batch_id'] in reverse:
            snapshots[reverse[manifest['batch_id']]]=original['versions_after']
        if manifest['batch_id'] in ('duplicate_r2','old_revision_r1') and result['versions_before']!=result['versions_after']:
            raise AssertionError('Duplicata/revisão antiga alterou versões S3')
    versions=state.verify();before=state.read(versions)
    first_manifest,first_frames=packets[0]
    retry=state.apply(first_manifest,first_frames,indices,snapshot,policy,ctx.run_id)
    if versions!=retry['versions_after']:raise AssertionError('Retry criou commit S3 vazio')
    proofs={n:compare_rows(before[n],state.read()[n],before[n].columns) for n in plan['tables']}
    expected=reconstruct(histories,snapshot,policy)
    reconstruction={n:compare_rows(expected[n],state.read()[n],expected[n].columns) for n in plan['tables']}
    if not all(p['success'] for p in [*proofs.values(),*reconstruction.values()]):raise AssertionError('Replay S3 não reconcilia')
    frozen=state.freeze(snapshots,{'status':'passed','algorithm':'group_max_revision_join_distinct','tables':reconstruction})
    return state,frozen,{'reused_frozen_state':False,'batches':results,'retry':retry,'retry_proofs':proofs}


def _publish(ctx,client,registry,spark,source_frames,plan,counts,spec,identity,fingerprints,references,parent=None,hook=None):
    def build(tx):
        tx.details['references']=references
        silver=prepare_silver(tx,source_frames,plan,counts)
        tx.hook('between_silver_and_gold')
        prepare_gold(tx,silver,spec,parent=parent)
    return publish_object_snapshot(ctx,client,registry,spark,identity,fingerprints,build,hook=hook)


def run_objects_demo(ctx,spark,service,*,selection,f04_relative,f06_relative):
    started=time.perf_counter();output=ctx.repo_root/'artifacts/f08/runs'/(ctx.run_id+'.json')
    report={'run_id':ctx.run_id,'selection_id':selection,'status':'running','stage':'configuration'}
    try:
        fingerprints={p:sha256(ctx.repo_root/p) for p in CODE+CONFIG}
        client=ObjectClient(ctx.repo_root);registry=registry_key(client,selection)
        runtime=_runtime(ctx.repo_root,spark)
        report.update(fingerprints=fingerprints,runtime=runtime,endpoint=client.config['endpoint'],bucket=client.bucket,
                      registry=registry,publications={},snapshots={})
        source_path=local(ctx.repo_root,f04_relative);source=json.loads(source_path.read_text())
        gold_path=local(ctx.repo_root,f06_relative);gold_report=json.loads(gold_path.read_text())
        if gold_report.get('status')!='passed' or gold_report['selection_id']!=selection:raise ValueError('Comparador F06 não aprovado')
        f06_hash=sha256(gold_path);gold_source_key=client.config['prefix']+'/references/f06_'+f06_hash+'.json'
        client.put_new(gold_source_key,gold_path.read_bytes())
        spec=load_gold_contract(ctx.repo_root/'configs/contracts/gold_v1.yaml',ctx.repo_root/'configs/contracts/silver_managed_v2.yaml')
        load_managed_contract(ctx.repo_root/'configs/contracts/silver_managed_v2.yaml',ctx.repo_root/'configs/contracts/silver_initial_v1.yaml')
        policy,snapshot=load_silver_policy(ctx.repo_root/'configs/silver_policy_v1.yaml',
            ctx.repo_root/'configs/contracts/home_credit_v1.yaml',ctx.repo_root/'notebooks/analise_silver.ipynb')
        bound=bind_sample(ctx,selection)
        with _ingestion_lock(local_path(ctx.repo_root,client.config['control_directory']),'.demo.lock'):
            report['capabilities']=capability_probe(ctx.repo_root)
            report['listeners']=service.listeners()
            if any(r['host']!='127.0.0.1' for r in report['listeners']):raise AssertionError('Porta do serviço exposta fora do host')
            with open_f04_snapshots(ctx,spark,selection,f04_relative) as (filesystem_silver,plan):
                report['stage']='mirror_inputs'
                mirror,mirror_key=mirror_inputs(ctx,client,bound,source_path)
                report['mirror']={'key':mirror_key,'mirror_id':mirror['mirror_id'],'files':len(mirror['files']),
                                  'bytes':sum(f['bytes'] for f in mirror['files'].values())}
                with open_bronze_snapshot(bound,spark) as loaded:
                    bronze_proofs={}
                    for table in TABLES:
                        relative=bound.ctx.bronze_dir.relative_to(ctx.repo_root).as_posix()+'/'+table
                        mirrored=spark.read.parquet(mirrored_directory(client,mirror,relative))
                        bronze_proofs[table]=compare_rows(loaded.frames[table],mirrored,loaded.frames[table].columns)
                    if not all(p['success'] for p in bronze_proofs.values()):raise AssertionError('Bronze mirror S3 difere da origem')
                    report['bronze_mirror_proofs']=bronze_proofs
                report['stage']='native_s3a_incremental_replay'
                state,frozen,replay=replay_objects(ctx,client,spark,mirror,mirror_key,source,plan,snapshot,policy,fingerprints,runtime)
                report.update(state_prefix=state.prefix,frozen_state=frozen,replay=replay)
                source_proofs={label:{n:compare_rows(fs['frames'][n],state.read(frozen['snapshots'][label])[n],fs['frames'][n].columns)
                    for n in plan['tables']} for label,fs in filesystem_silver.items()}
                if not all(p['success'] for group in source_proofs.values() for p in group.values()):raise AssertionError('Silver nativa S3 diverge da F04')
                report['silver_fs_s3_proofs']=source_proofs
                parent=None
                for label in ('baseline','corrected','late'):
                    report['stage']='publish_'+label
                    source_frames=state.read(frozen['snapshots'][label])
                    input_refs=[{'key':mirror_key,'sha256':client.checksum(mirror_key)},
                        {'key':state.prefix+'/_FROZEN.json','sha256':client.checksum(state.prefix+'/_FROZEN.json')},
                        {'key':gold_source_key,'sha256':f06_hash}]
                    parent_ref=None
                    if parent:
                        key=registry+'/manifests/'+parent['manifest']['publication_id']+'.json'
                        parent_ref={'key':key,'sha256':client.checksum(key)};input_refs.append(parent_ref)
                    identity={'scope':'object_analytics_v1','selection_id':selection,'snapshot':label,
                        'input_references':input_refs,'parent_publication':parent_ref,
                        'source_versions':frozen['snapshots'][label],'code_and_configuration':fingerprints,'runtime':runtime}
                    kwargs={'source_frames':source_frames,'plan':plan,'counts':filesystem_silver[label]['counts'],
                        'spec':spec,'identity':identity,'fingerprints':fingerprints,'references':input_refs,'parent':parent}
                    publication_id=digest(identity)[:24]
                    if label=='corrected' and not client.exists(registry+'/manifests/'+publication_id+'.json'):
                        before=current(client,registry)[0]
                        try:_publish(RunContext.create(ctx.repo_root),client,registry,spark,**kwargs,hook=fail_at('after_commit:gold.abt:merge'))
                        except InjectedFailure:
                            if current(client,registry)[0]!=before:raise AssertionError('Falha S3 expôs publicação parcial')
                            report['post_commit_failure_preserved_current']=True
                        else:raise AssertionError('Falha deliberada S3 não ocorreu')
                    manifest,attempt=_publish(RunContext.create(ctx.repo_root),client,registry,spark,**kwargs)
                    checked,frames=verify_publication(client,registry,manifest['publication_id'],spark)
                    _,fs_frames=verify_manifest(ctx.repo_root,ctx.repo_root/gold_report['registry'],gold_report['publications'][label],spark)
                    proofs={n:compare_rows(fs_frames[n],frame,fs_frames[n].columns) for n,frame in frames.items()}
                    if not all(p['success'] for p in proofs.values()):raise AssertionError('Publicação S3 difere dos dados FS aprovados')
                    report['publications'][label]=manifest['publication_id']
                    report['snapshots'][label]={'tables':manifest['tables'],'validations':manifest['validations'],
                        'gold_update':manifest['details']['gold_update'],'fs_comparison':proofs,'attempt':attempt}
                    parent={'manifest':checked,'frames':frames,'silver':{n:frames['silver.'+n] for n in plan['tables']}}
                report['stage']='historical_rollback'
                baseline,late=(report['publications'][n] for n in ('baseline','late'))
                activate_object_publication(RunContext.create(ctx.repo_root),client,registry,spark,baseline)
                with open_object_publication(client,registry,spark) as (historical,frames):
                    _,fs_frames=verify_manifest(ctx.repo_root,ctx.repo_root/gold_report['registry'],gold_report['publications']['baseline'],spark)
                    report['historical_proofs']={n:compare_rows(fs_frames[n],frames[n],fs_frames[n].columns)
                        for n in ('gold.abt','gold.monthly_metrics')}
                    if not all(p['success'] for p in report['historical_proofs'].values()):raise AssertionError('Histórico S3 não reproduz baseline')
                activate_object_publication(RunContext.create(ctx.repo_root),client,registry,spark,late)
                report['stage']='retry_and_service_restart'
                previous=current(client,registry)[0]
                source_frames=state.read(frozen['snapshots']['late'])
                corrected_manifest,corrected_frames=verify_publication(client,registry,report['publications']['corrected'],spark)
                late_manifest,late_frames=verify_publication(client,registry,late,spark)
                parent={'manifest':corrected_manifest,'frames':corrected_frames,
                        'silver':{n:corrected_frames['silver.'+n] for n in plan['tables']}}
                _,retry=_publish(RunContext.create(ctx.repo_root),client,registry,spark,source_frames=source_frames,
                    plan=plan,counts=filesystem_silver['late']['counts'],spec=spec,identity=late_manifest['identity'],
                    fingerprints=fingerprints,references=late_manifest['references'],parent=parent)
                if not retry['reused']:raise AssertionError('Retry publicou outra cópia S3')
                report['retry']=retry
                service.stop()
                try:client.get(registry+'/_CURRENT.json')
                except Exception as error:report['service_outage_observed']=type(error).__name__
                else:raise AssertionError('Leitura deveria falhar com serviço parado')
                service.start()
                if current(client,registry)[0]!=previous:raise AssertionError('Reinício modificou CURRENT')
                with open_object_publication(client,registry,spark,late) as (_,restored):
                    report['restart_proofs']={n:compare_rows(frame,restored[n],frame.columns) for n,frame in late_frames.items()}
                    if not all(p['success'] for p in report['restart_proofs'].values()):raise AssertionError('Reinício perdeu dados S3')
                    report['abt_rows']=restored['gold.abt'].count()
                    report['monthly_metrics']=[r.asDict() for r in restored['gold.monthly_metrics'].orderBy('MONTH').collect()]
                verify_mirror(client,mirror);state.verify_frozen()
                report['retention_audit']={}
                for label,publication_id in report['publications'].items():
                    manifest,_=verify_publication(client,registry,publication_id,spark)
                    for entry in manifest['tables'].values():spark.read.format('delta').option('versionAsOf',0).load(entry['uri']).count()
                    report['retention_audit'][label]={'status':'passed','current_and_initial_versions_readable':True,'pins':'indefinite'}
                report['current_publication']=current(client,registry)[0]['publication_id']
                report['bucket_logical_bytes']=sum(client.list(client.config['prefix']+'/').values())
        if sha256(gold_path)!=f06_hash or any(sha256(ctx.repo_root/p)!=h for p,h in fingerprints.items()):raise RuntimeError('Entrada/implementação mudou durante F08')
        report.update(status='passed',stage='complete',duration_seconds=round(time.perf_counter()-started,3))
    except BaseException as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error),duration_seconds=round(time.perf_counter()-started,3))
        atomic_json(output,report);raise
    atomic_json(output,report)
    return {'status':'passed','run_id':ctx.run_id,'report':str(output),'publications':report['publications'],
            'abt_rows':report['abt_rows'],'duration_seconds':report['duration_seconds']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',required=True);parser.add_argument('--f04-report',required=True);parser.add_argument('--f06-report',required=True)
    parser.add_argument('--keep-service',action='store_true')
    args=parser.parse_args();ctx=RunContext.create(Path(__file__).resolve().parents[2]);service=ObjectService(ctx.repo_root)
    service.start();spark=None
    try:
        spark=create_object_spark(ctx.repo_root,app_name='f08-objects-demo')
        result=run_objects_demo(ctx,spark,service,selection=args.sample,f04_relative=args.f04_report,f06_relative=args.f06_report)
    finally:
        if spark is not None:spark.stop()
        if not args.keep_service:service.stop()
    print(json.dumps(result))


if __name__=='__main__':main()
