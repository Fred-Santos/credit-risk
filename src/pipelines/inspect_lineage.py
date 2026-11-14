"""Auditar lineage de uma operação aprovada, sem ativar ou modificar tabelas."""
import argparse
import json
from pathlib import Path
from src.operation.lineage import audit
from src.object_store.client import ObjectClient
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.utils.run_context import RunContext


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation-report',required=True)
    args=parser.parse_args();ctx=RunContext.create(Path(__file__).resolve().parents[2])
    service=ObjectService(ctx.repo_root);owned=service.status()['status']!='running';spark=None
    try:
        service.start();spark=create_object_spark(ctx.repo_root,app_name='lakehouse-lineage-audit')
        result=audit(ctx,ObjectClient(ctx.repo_root),spark,args.operation_report)
    finally:
        if spark is not None:spark.stop()
        if owned:service.stop()
    print(json.dumps(result))


if __name__=='__main__':main()
