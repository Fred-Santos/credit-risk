"""Perfil exato das fontes adquiridas; não publica nem altera camadas."""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from pyspark.sql import functions as F
from src.profiling.frame_profile import profile_frame
from src.utils.paths import load_paths
from src.utils.spark import create_spark_session
from scripts.acquire_expansion import load_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-seconds', type=int, default=0, help='Tempo máximo por tabela aguardando aquisição em andamento')
    parser.add_argument('--spark-config', type=Path, default=None, help='Perfil explícito; padrão preserva o perfil original')
    parser.add_argument('--output', type=Path, default=None, help='Novo relatório; não sobrescreve destino explícito')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog, _ = load_files(root)
    raw = load_paths(root)['raw_dir']
    output = root / (args.output or Path('artifacts/expansion/source_profiles.json'))
    if args.output is not None and output.exists():
        raise FileExistsError('Destino explícito já existe; preservar evidência anterior')
    if args.spark_config is not None and args.output is None:
        raise ValueError('Outro perfil requer --output para preservar a evidência E00')
    output.parent.mkdir(parents=True, exist_ok=True)
    definitions = {r['Variable'] for r in csv.DictReader((raw / catalog['dictionary']).open())}
    structural = {'case_id', 'num_group1', 'num_group2', 'MONTH', 'WEEK_NUM', 'target', 'date_decision'}
    report = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'tables': {}, 'status': 'running'}
    spark = create_spark_session(root, app_name='credit-risk-expansion-source-profile', config_path=args.spark_config)
    started = time.monotonic()
    try:
        base = spark.read.parquet(str(raw / 'parquet_files/train/train_base.parquet'))
        base_keys = base.select('case_id').cache()
        cohort = base.where("date_decision >= '2020-01-01' AND date_decision < '2020-10-01'").select('case_id').cache()
        for name, shards in catalog['tables'].items():
            paths = [str(raw / s['name']) for s in shards]
            deadline = time.monotonic() + args.wait_seconds
            while not all(Path(p).exists() for p in paths):
                if time.monotonic() >= deadline:
                    raise FileNotFoundError(f'Aquisição incompleta: {name}')
                time.sleep(2)
            schemas = [spark.read.parquet(p).schema for p in paths]
            equal = all(s == schemas[0] for s in schemas)
            if not equal:
                raise ValueError(f'Schemas divergentes em {name}; não fazer merge implícito')
            df = spark.read.parquet(*paths)
            key = [c for c in ('case_id', 'num_group1', 'num_group2') if c in df.columns]
            result = profile_frame(df, key)
            result['key_status'] = 'candidate_observed_not_business_contract'
            result['shard_schemas_equal'] = equal
            keys = df.select('case_id').distinct()
            result['orphan_cases'] = keys.join(base_keys,'case_id','left_anti').count()
            result['base_cases_without_match'] = base_keys.join(keys,'case_id','left_anti').count()
            selected = df.join(cohort,'case_id','left_semi')
            result['cohort_rows'] = selected.count()
            result['cohort_distinct_cases'] = selected.select('case_id').distinct().count()
            result['max_rows_per_case'] = df.groupBy('case_id').count().agg(F.max('count')).first()[0]
            result['features_without_definition'] = sorted(set(df.columns)-definitions-structural)
            date_cols = [c for c in df.columns if c.endswith('D') or c == 'date_decision']
            if date_cols:
                expr=[]
                for i,c in enumerate(date_cols):
                    expr.extend([F.min(c).alias(f'min_{i}'), F.max(c).alias(f'max_{i}')])
                dates=df.agg(*expr).first().asDict()
                result['raw_date_ranges']={c:{'min':dates[f'min_{i}'],'max':dates[f'max_{i}']} for i,c in enumerate(date_cols)}
            # Metadados de rodapé: bytes de column chunks, sem carregar linhas no driver.
            uncompressed = 0
            for path in paths:
                reader = spark._jvm.org.apache.parquet.hadoop.ParquetFileReader.readFooter(
                    spark._jsc.hadoopConfiguration(), spark._jvm.org.apache.hadoop.fs.Path(path))
                blocks = reader.getBlocks()
                for i in range(blocks.size()):
                    uncompressed += blocks.get(i).getTotalByteSize()
            result['parquet_uncompressed_column_bytes'] = uncompressed
            result['compressed_file_bytes'] = sum(s['bytes'] for s in shards)
            report['tables'][name]=result
            report['duration_seconds']=round(time.monotonic()-started,3)
            output.write_text(json.dumps(report,indent=2,default=str)+'\n')
            print(f"{name}: {result['rows']} linhas; chave candidata: {key}; duplicatas: {result['duplicate_key_groups']}",flush=True)
        report['status']='completed'
        report['duration_seconds']=round(time.monotonic()-started,3)
        output.write_text(json.dumps(report,indent=2,default=str)+'\n')
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
