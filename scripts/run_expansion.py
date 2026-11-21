"""Executa etapas da expansão em processo Spark novo com perfil de 8 GiB."""
import argparse
import json
from pathlib import Path
import uuid
import yaml
from src.utils.spark import create_spark_session,load_spark_settings
from src.expansion.silver import build_silver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['silver','audit','gold','revision-demo','analysis'])
    parser.add_argument('--bronze-id')
    parser.add_argument('--silver-id')
    parser.add_argument('--gold-id')
    args=parser.parse_args()
    for identifier in (args.bronze_id,args.silver_id,args.gold_id):
        if identifier is not None and (len(identifier)!=24 or any(c not in '0123456789abcdef' for c in identifier)):raise ValueError('ID inválido')
    if args.phase=='silver' and not args.bronze_id:parser.error('--bronze-id obrigatório')
    if args.phase!='silver' and not args.silver_id:parser.error('--silver-id obrigatório')
    if args.phase=='analysis' and not args.gold_id:parser.error('--gold-id obrigatório')
    repo=Path(__file__).resolve().parents[1]
    runtime=repo/'artifacts/expansion/runs'/uuid.uuid4().hex;runtime.mkdir(parents=True)
    settings=load_spark_settings(repo/'configs/spark_expansion.yaml')
    settings['config']['spark.databricks.delta.snapshotPartitions']=settings['config']['spark.sql.shuffle.partitions']
    settings['config']['spark.local.dir']=str(repo/'.runtime/tmp/expansion-stages'/runtime.name)
    config=runtime/'spark.yaml';config.write_text(yaml.safe_dump({'spark':settings},sort_keys=False))
    spark=create_spark_session(repo,app_name='expansion-'+args.phase,delta=True,config_path=config)
    try:
        heap=spark._jvm.java.lang.Runtime.getRuntime().maxMemory()
        if abs(heap-8*1024**3)>64*1024**2:raise RuntimeError('Heap diverge de 8 GiB')
        contract=repo/'configs/contracts/expansion_silver_v1.yaml'
        if args.phase=='silver':
            result,reused=build_silver(repo,spark,repo/'data/bronze/expansion'/args.bronze_id,contract)
        else:
            silver=repo/'data/silver/expansion'/args.silver_id
            audit_path=repo/'artifacts/expansion/temporal'/(args.silver_id+'.json')
            if args.phase=='audit':
                from src.expansion.temporal import audit_temporal
                if audit_path.exists():
                    result=json.loads(audit_path.read_text());reused=True
                    from src.pipelines.download_home_credit import sha256
                    if result['silver_manifest_sha256']!=sha256(silver/'_silver.json') or result['status']!='passed':raise ValueError('Auditoria anterior inválida')
                else:result=audit_temporal(repo,spark,silver,contract,output=audit_path);reused=False
                result={**result,'id':args.silver_id}
            elif args.phase=='analysis':
                from src.expansion.analysis import build_analysis
                result,reused=build_analysis(repo,spark,silver,repo/'data/gold/expansion'/args.gold_id,repo/'configs/expansion_analysis_v1.yaml')
            elif args.phase=='gold':
                from src.expansion.gold import build_gold
                from src.bronze.expansion import load_temporal_policy
                result,reused=build_gold(repo,spark,silver,contract,repo/'configs/expansion_features_v1.yaml',
                    repo/'configs/contracts/expansion_gold_v1.yaml',load_temporal_policy(repo/'configs/temporal_policy_v1.yaml'),audit_path=audit_path)
            else:
                from scripts.simulate_expansion_revision import simulate
                result,reused=simulate(repo,spark,silver,contract)
        receipt={'phase':args.phase,'id':result['id'],'status':result['status'],'reused':reused,
            'runtime':str(runtime.relative_to(repo)),'heap_bytes':heap}
        (runtime/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)
    finally:spark.stop()


if __name__=='__main__':main()
