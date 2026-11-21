"""Diagnóstico pontual da Bronze, sem sobrescrever a fonte ou aprovar Silver."""
import argparse
from pathlib import Path
import uuid
from src.expansion.silver import load_contract
from src.expansion.rejections import diagnose
from src.pipelines.download_home_credit import sha256
from src.utils.spark import create_spark_session


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bronze-id',required=True);p.add_argument('--table',required=True);a=p.parse_args()
    if len(a.bronze_id)!=24 or any(c not in '0123456789abcdef' for c in a.bronze_id):raise ValueError('ID inválido')
    root=Path(__file__).resolve().parents[1];contract=load_contract(root/'configs/contracts/expansion_silver_v1.yaml')
    if a.table not in contract['tables']:raise ValueError('Tabela desconhecida')
    source=root/'data/bronze/expansion'/a.bronze_id
    spark=create_spark_session(root,config_path=Path('configs/spark_expansion.yaml'))
    try:
        result=diagnose(spark.read.parquet(str(source/'tables'/a.table)),contract['tables'][a.table],
            root/'artifacts/expansion/rejections'/uuid.uuid4().hex,source_manifest_sha256=sha256(source/'_bronze.json'))
        print(result)
    finally:spark.stop()


if __name__=='__main__':main()
