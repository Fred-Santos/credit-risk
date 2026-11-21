"""E01: carga real e prova Delta/S3 em namespace privado; nenhum CURRENT."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import time
import uuid
import yaml
from pyspark.sql import functions as F
from src.object_store.client import ObjectClient
from src.object_store.fixtures import temporary_objects
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.pipelines.download_home_credit import sha256
from src.utils.paths import load_paths
from src.utils.spark import load_spark_settings
from scripts.acquire_expansion import load_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default=uuid.uuid4().hex)
    args = parser.parse_args()
    if not args.run_id.isalnum():
        raise ValueError('run-id deve ser alfanumérico')
    root = Path(__file__).resolve().parents[1]
    out = root / 'artifacts/expansion/e01' / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    scratch = root / '.runtime/tmp/expansion' / args.run_id
    scratch.mkdir(parents=True, exist_ok=False)
    events = out / 'events'; events.mkdir()
    profile = root / 'configs/spark_expansion.yaml'
    settings = load_spark_settings(profile)
    settings['config'].update({'spark.local.dir': str(scratch),
        'spark.eventLog.enabled': 'true', 'spark.eventLog.dir': events.as_uri(),
        'spark.eventLog.compress': 'false'})
    effective = out / 'spark_effective.yaml'
    effective.write_text(yaml.safe_dump({'spark': settings}, sort_keys=False))
    report = {'run_id': args.run_id, 'status': 'running', 'config': settings,
              'profile_sha256': sha256(profile), 'stages': {}, 'outputs': {}}
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2, default=str)+'\n')
    service = ObjectService(root)
    previous = service.status()['status'] == 'running'
    spark = None
    started = time.monotonic()
    try:
        service.start()
        spark = create_object_spark(root, app_name='credit-risk-expansion-e01', config_path=effective)
        heap = spark._jvm.java.lang.Runtime.getRuntime().maxMemory()
        report['runtime'] = {'jvm_max_heap_bytes': heap,
            'configured_driver_memory': spark.sparkContext.getConf().get('spark.driver.memory'),
            'spark': spark.version, 'java': spark._jvm.java.lang.System.getProperty('java.version'),
            'hadoop': spark._jvm.org.apache.hadoop.util.VersionInfo.getVersion(),
            'delta': importlib.metadata.version('delta-spark')}
        if abs(heap - 8 * 1024**3) > 64 * 1024**2:
            raise RuntimeError('Heap efetivo diverge de 8 GiB; perfil não aplicado')
        save()
        raw = load_paths(root)['raw_dir']
        catalog, _ = load_files(root)
        source = 'train_credit_bureau_a_2'
        frame = spark.read.parquet(*[str(raw / f['name']) for f in catalog['tables'][source]])
        stage = time.monotonic()
        grouped = frame.groupBy('case_id', 'num_group1').agg(F.count('*').alias('observations'))
        target = out / 'bureau_groups_delta'
        grouped.write.format('delta').mode('errorifexists').save(str(target))
        reloaded = spark.read.format('delta').load(str(target))
        aggregate = reloaded.agg(F.sum('observations').alias('source_rows'),
                                 F.count('*').alias('groups')).first().asDict()
        expected = json.loads((root / 'artifacts/expansion/source_profiles.json').read_text())['tables'][source]
        if aggregate['source_rows'] != expected['rows']:
            raise AssertionError('Agregação não reconcilia com E00')
        per_case = reloaded.groupBy('case_id').agg(F.sum('observations').alias('n'))
        per_case_stats = per_case.agg(F.count('*').alias('cases'), F.max('n').alias('max_rows_per_case')).first().asDict()
        if per_case_stats['max_rows_per_case'] != expected['max_rows_per_case']:
            raise AssertionError('Histórico máximo diverge de E00')
        report['stages']['largest_history'] = {'duration_seconds': round(time.monotonic()-stage,3),
            **aggregate, **per_case_stats, 'input_files': len(catalog['tables'][source])}
        report['outputs']['local_delta'] = str(target.relative_to(root))
        save(); print('Maior histórico agregado e reconciliado', flush=True)
        stage = time.monotonic()
        wide = spark.read.parquet(*[str(raw / f['name']) for f in catalog['tables']['train_static_0']])
        counts = wide.agg(F.count('*').alias('_rows'), *[
            F.count(F.col(c)).alias(f'c{i}') for i,c in enumerate(wide.columns)]).first().asDict()
        if counts['_rows'] != 1526659:
            raise AssertionError('Leitura larga não reconcilia com E00')
        report['stages']['wide_table'] = {'duration_seconds': round(time.monotonic()-stage,3),
            'rows': counts['_rows'], 'columns_scanned': len(wide.columns)}
        stage = time.monotonic()
        with temporary_objects(root) as client:
            prefix = client.config['prefix']
            uri = client.uri(prefix+'/e01_delta')
            spark.range(10).write.format('delta').mode('errorifexists').save(uri)
            spark.range(10,15).write.format('delta').mode('append').save(uri)
            current = spark.read.format('delta').load(uri).count()
            initial = spark.read.format('delta').option('versionAsOf',0).load(uri).count()
            if (current, initial) != (15,10):
                raise AssertionError('Roundtrip Delta S3 ou leitura histórica inválida')
            report['stages']['delta_s3'] = {'duration_seconds':round(time.monotonic()-stage,3),
                'current_rows':current, 'version_0_rows':initial, 'synthetic':True,
                'objects':len(client.list(prefix+'/'))}
        report['s3_fixture_removed'] = not ObjectClient(root).list(prefix+'/')
        if not report['s3_fixture_removed']:
            raise AssertionError('Fixture S3 não removida')
        report['status'] = 'passed'
    except BaseException as exc:
        report['status'] = 'failed'
        report['error_type'] = type(exc).__name__
        raise
    finally:
        if spark is not None: spark.stop()
        if not previous: service.stop()
        report['duration_seconds'] = round(time.monotonic()-started,3)
        report['service_preexisting'] = previous
        # Event logs locais: métricas por tarefa, incluindo tentativas/reexecuções.
        totals = {'disk_spilled_bytes':0, 'memory_spilled_bytes':0, 'shuffle_write_bytes':0,
                  'shuffle_read_bytes':0, 'tasks':0}
        for path in events.rglob('*'):
            if not path.is_file() or path.name.startswith('.'): continue
            for line in path.open():
                event = json.loads(line)
                if event.get('Event') != 'SparkListenerTaskEnd': continue
                metrics = event.get('Task Metrics', {})
                totals['tasks'] += 1
                totals['disk_spilled_bytes'] += metrics.get('Disk Bytes Spilled',0)
                totals['memory_spilled_bytes'] += metrics.get('Memory Bytes Spilled',0)
                totals['shuffle_write_bytes'] += metrics.get('Shuffle Write Metrics',{}).get('Shuffle Bytes Written',0)
                read = metrics.get('Shuffle Read Metrics',{})
                totals['shuffle_read_bytes'] += read.get('Remote Bytes Read',0)+read.get('Local Bytes Read',0)
        report['task_metrics'] = totals
        save()
        print(json.dumps({'report':str(out/'report.json'),'status':report['status']}),flush=True)


if __name__ == '__main__':
    main()
