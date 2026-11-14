"""Consultar ou selecionar uma publicação S3 já aprovada; sem manutenção destrutiva."""
import argparse
import json
from pathlib import Path

from src.object_store.client import ObjectClient
from src.object_store.publication import registry_key,open_object_publication,activate_object_publication
from src.object_store.spark import create_object_spark
from src.utils.run_context import RunContext


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['inspect','activate'])
    parser.add_argument('--sample',required=True)
    parser.add_argument('--publication',help='ID explícito; obrigatório para ativar')
    args=parser.parse_args()
    if args.action=='activate' and not args.publication:parser.error('activate exige --publication')
    ctx=RunContext.create(Path(__file__).resolve().parents[2]);client=ObjectClient(ctx.repo_root)
    registry=registry_key(client,args.sample)
    spark=create_object_spark(ctx.repo_root,app_name='f08-object-consumer')
    try:
        if args.action=='activate':
            result=activate_object_publication(ctx,client,registry,spark,args.publication)
        else:
            with open_object_publication(client,registry,spark,args.publication) as (manifest,frames):
                result={'status':'passed','publication_id':manifest['publication_id'],
                    'tables':{name:{k:t[k] for k in ('uri','delta_table_id','version','rows')} for name,t in manifest['tables'].items()},
                    'monthly_metrics':[r.asDict() for r in frames['gold.monthly_metrics'].orderBy('MONTH').collect()]}
    finally:spark.stop()
    print(json.dumps(result))


if __name__=='__main__':main()
