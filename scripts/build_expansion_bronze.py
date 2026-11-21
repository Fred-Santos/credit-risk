"""E02: seleção temporal completa e Bronze reconciliada em namespace próprio."""
import json
import uuid
import yaml
from pathlib import Path
from scripts.acquire_expansion import load_files
from src.bronze.expansion import load_temporal_policy, build_temporal_bronze
from src.utils.spark import create_spark_session, load_spark_settings


def main():
    root = Path(__file__).resolve().parents[1]
    catalog, _ = load_files(root)
    policy = load_temporal_policy(root/'configs/temporal_policy_v1.yaml')
    run_id = uuid.uuid4().hex
    runtime = root/'artifacts/expansion/bronze_runs'/run_id
    runtime.mkdir(parents=True,exist_ok=False)
    settings = load_spark_settings(root/'configs/spark_expansion.yaml')
    settings['config']['spark.local.dir'] = str(root/'.runtime/tmp/bronze-expansion'/run_id)
    effective = runtime/'spark_effective.yaml'
    effective.write_text(yaml.safe_dump({'spark':settings},sort_keys=False))
    spark = create_spark_session(root, app_name='credit-risk-expansion-bronze',config_path=effective)
    try:
        heap = spark._jvm.java.lang.Runtime.getRuntime().maxMemory()
        if abs(heap-8*1024**3)>64*1024**2:
            raise RuntimeError('Heap efetivo diverge de 8 GiB')
        manifest, reused = build_temporal_bronze(root,spark,catalog,policy)
        summary = {'selection_id':manifest['selection_id'],'status':manifest['status'],
            'reused':reused,'population':manifest['population'],
            'tables':{n:v['bronze_rows'] for n,v in manifest['tables'].items()},
            'jvm_max_heap_bytes':heap,'spark_config':settings,'runtime_id':run_id}
        out = root/'artifacts/expansion/bronze'
        out.mkdir(parents=True,exist_ok=True)
        (out/(manifest['selection_id']+('-reused' if reused else '')+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
