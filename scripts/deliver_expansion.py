"""E07: entrega S3 local, matriz de recuperação e consumidor independente."""
import argparse
import json
from pathlib import Path
import uuid
import yaml
from src.expansion.publication import expansion_client,consume,registry
from src.expansion.delivery import exercise
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.object_store.publication import current
from src.expansion.storage import verify_package
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json
from src.utils.spark import load_spark_settings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['deliver','consume'])
    for name in ('silver','gold','analysis','corrected-silver','corrected-gold','corrected-analysis'):
        p.add_argument('--'+name+'-id')
    p.add_argument('--selection-id');p.add_argument('--publication-id')
    args=p.parse_args()
    for name,value in vars(args).items():
        if name.endswith('_id') and value is not None and (len(value)!=24 or any(c not in '0123456789abcdef' for c in value)):raise ValueError('ID inválido')
    root=Path(__file__).resolve().parents[1]
    service=ObjectService(root);service.start()
    run=root/'artifacts/expansion/e07_runs'/uuid.uuid4().hex;run.mkdir(parents=True)
    settings=load_spark_settings(root/'configs/spark_expansion.yaml')
    settings['config']['spark.local.dir']=str(root/'.runtime/tmp/expansion-delivery'/run.name)
    config=run/'spark.yaml';config.write_text(yaml.safe_dump({'spark':settings},sort_keys=False))
    spark=create_object_spark(root,app_name='expansion-delivery-'+args.action,config_path=config)
    client=expansion_client(root)
    try:
        heap=spark._jvm.java.lang.Runtime.getRuntime().maxMemory()
        if abs(heap-8*1024**3)>64*1024**2:raise ValueError('Heap não corresponde a 8 GiB')
        if args.action=='deliver':
            if not all(getattr(args,n+'_id') for n in ('silver','gold','analysis','corrected_silver','corrected_gold','corrected_analysis')):
                p.error('deliver exige os seis IDs dos snapshots')
            baseline=(root/'data/silver/expansion'/args.silver_id,root/'data/gold/expansion'/args.gold_id,root/'data/gold/expansion-analysis'/args.analysis_id)
            corrected=(root/'data/silver/expansion'/args.corrected_silver_id,root/'data/gold/expansion'/args.corrected_gold_id,root/'data/gold/expansion-analysis'/args.corrected_analysis_id)
            # Uma execução do fluxo percorre todos os gates locais e publica o conjunto novo;
            # a origem real e os snapshots pesados já materializados são reutilizados.
            from src.bronze.expansion import verify_committed,source_fingerprints
            sm=verify_package(baseline[0],'_silver.json')
            selection=sm['identity']['bronze_selection_id'];bronze=root/'data/bronze/expansion'/selection
            bm=json.loads((bronze/'_bronze.json').read_text());verify_committed(bronze,bm['identity'])
            actual_raw=source_fingerprints(root/'data/raw',bm['identity']['catalog'])
            if actual_raw!=bm['identity']['sources']:raise ValueError('RAW diverge dos snapshots aprovados')
            mvp_before={key:client.checksum(key) for key in client.list('lakehouse-v1/') if key.endswith('/_CURRENT.json')}
            result=exercise(root,client,spark,baseline,corrected,run/'recovery.json')
            # Reinício real do serviço: nunca remove diretórios ou dados.
            service.stop();service.start()
            manifest,frames=consume(client,spark,selection,result['baseline_id'])
            if current(client,registry(client,selection))[0]['publication_id']!=result['baseline_id']:raise AssertionError('Reinício perdeu CURRENT')
            mvp_after={key:client.checksum(key) for key in client.list('lakehouse-v1/') if key.endswith('/_CURRENT.json')}
            if mvp_before!=mvp_after:raise AssertionError('CURRENT do MVP mudou')
            result.update(service_restart_passed=True,mvp_currents_preserved=True,mvp_current_count=len(mvp_before),
                selection_id=selection,published_tables=len(manifest['tables']),
                source_preflight={'raw_files_verified':len(actual_raw),'bronze_id':selection,
                    'silver_id':args.silver_id,'gold_id':args.gold_id,'analysis_id':args.analysis_id,
                    'local_snapshots_reused':True,'corrected_silver_id':args.corrected_silver_id},heap_bytes=heap)
            prefix=client.config['prefix']+'/published/'+selection+'/'
            objects=client.list(prefix)
            result['storage']={'objects':len(objects),'bytes':sum(objects.values()),'retained_publications':len([k for k in client.list(registry(client,selection)+'/manifests/') if k.endswith('.json')]),
                'real_vacuum':'forbidden','snapshots_pinned_indefinitely':True}
            atomic_json(root/'artifacts/expansion/e07_delivery.json',result)
        else:
            if not args.selection_id:p.error('consume exige --selection-id')
            manifest,frames=consume(client,spark,args.selection_id,args.publication_id)
            if 'gold.evaluation_labels' in frames or 'target' in frames['silver.train_base'].columns:raise AssertionError('Leitor padrão retornou rótulos individuais da reserva')
            reports=[r for r in manifest['references'] if r['local_source'].endswith('/report/report.json')]
            if len(reports)!=1:raise ValueError('Referência analítica ambígua')
            report=client.json(reports[0]['key'])
            expected={r['MONTH']:r for r in report['rows']['monthly']}
            monthly=[{k:(str(v) if k in ('first_date','last_date') and v is not None else v) for k,v in r.asDict().items()}
                     for r in frames['gold.analysis_monthly'].orderBy('MONTH').collect()]
            for row in monthly:
                for key,value in row.items():
                    v=str(value) if key in ('first_date','last_date') and value is not None else value
                    if v!=expected[row['MONTH']][key]:raise AssertionError('Consumo S3 diverge do relatório aprovado')
            result={'status':'passed','publication_id':manifest['publication_id'],'selection_id':args.selection_id,
                'published_tables':len(manifest['tables']),'returned_tables':len(frames),'individual_holdout_labels_hidden':True,
                'monthly':monthly,'independent_process':True,'data_source':'S3 API and S3A only, no local data read',
                'ml_ready':False,'is_simulated':manifest['identity']['is_simulated']}
            atomic_json(root/'artifacts/expansion/e07_independent_consumer.json',result)
        atomic_json(run/'result.json',result)
        print(json.dumps({'status':result['status'],'run':str(run.relative_to(root)),
            'publication_id':result.get('publication_id',result.get('baseline_id'))}),flush=True)
    finally:spark.stop()
    # Serviço permanece disponível para consumo dos ponteiros aprovados.


if __name__=='__main__':main()
