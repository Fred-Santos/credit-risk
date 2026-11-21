"""Bronze temporal imutável: todas as auxiliares dos casos, RAW intacta."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import uuid
import yaml

from src.bronze.build_bronze import _ingestion_lock, _output_checksums
from src.pipelines.download_home_credit import COMPETITION, sha256
from src.quality.reconcile_bronze import compare_rows


METADATA = ['_source_file', '_selection_id', '_run_id', '_ingested_at_utc']


def load_temporal_policy(path):
    policy = yaml.safe_load(Path(path).read_text())
    expected = {'version', 'scope', 'base_table', 'decision_column', 'selection',
                'auxiliary_selection', 'windows'}
    if not isinstance(policy, dict) or set(policy) != expected:
        raise ValueError('Campos inválidos na política temporal')
    if (type(policy['version']) is not int or policy['version'] != 1
            or policy['scope'] != 'home_credit_train_2020'
            or policy['base_table'] != 'train_base' or policy['decision_column'] != 'date_decision'
            or policy['selection'] != 'all_eligible_cases'
            or policy['auxiliary_selection'] != 'all_rows_for_selected_case_ids'):
        raise ValueError('Política temporal não suportada')
    windows = policy['windows']
    if not isinstance(windows, dict) or set(windows) != {'development','evaluation','public'}:
        raise ValueError('Janelas obrigatórias ausentes')
    for window in windows.values():
        if not isinstance(window, dict) or set(window) != {'start_inclusive','end_exclusive'}:
            raise ValueError('Limites inválidos')
        for value in window.values():
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError('Datas devem ser ISO explícitas')
        if window['start_inclusive'] >= window['end_exclusive']:
            raise ValueError('Janela vazia ou invertida')
    dev, evaluation, public = (windows[n] for n in ('development','evaluation','public'))
    if (dev['end_exclusive'] != evaluation['start_inclusive']
            or public['start_inclusive'] != dev['start_inclusive']
            or public['end_exclusive'] != evaluation['end_exclusive']):
        raise ValueError('Janelas devem ser contíguas e formar a população pública')
    return policy


def source_fingerprints(raw, catalog):
    """Confere todos os bytes com o journal sem chamar a rede ou alterar RAW."""
    sources = {}
    for remote in [catalog['dictionary']] + [s['name'] for shards in catalog['tables'].values() for s in shards]:
        path = raw / remote
        journal = raw / '_acquisition' / (hashlib.sha256(remote.encode()).hexdigest()+'.json')
        record = json.loads(journal.read_text())
        digest = sha256(path)
        if (record['competition'] != COMPETITION or record['remote'] != remote
                or record['status'] != 'complete' or record['sha256'] != digest
                or record['bytes'] != path.stat().st_size):
            raise ValueError(f'Fonte diverge do journal: {remote}')
        sources[remote] = {'sha256':digest,'bytes':path.stat().st_size}
    for shards in catalog['tables'].values():
        for shard in shards:
            if sources[shard['name']]['bytes'] != shard['bytes']:
                raise ValueError('Tamanho diverge do catálogo')
    return sources


def verify_committed(destination, identity):
    manifest = json.loads((destination / '_bronze.json').read_text())
    digest = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    if (manifest['identity'] != identity or manifest['status'] != 'passed'
            or manifest['identity_sha256'] != digest or manifest['selection_id'] != digest[:24]
            or destination.name != digest[:24]
            or manifest['output_checksums'] != _output_checksums(destination)):
        raise RuntimeError('Bronze alterada ou identidade divergente; não sobrescrever')
    expected = set(identity['catalog']['tables'])
    if set(manifest['tables']) != expected or not all(v['reconciliation']['success'] for v in manifest['tables'].values()):
        raise RuntimeError('Bronze sem reconciliação completa')
    if any(not any((destination/'tables'/name).glob('*.parquet')) for name in expected):
        raise RuntimeError('Tabela Bronze ausente')
    return manifest


def read_logical(spark, raw, shards):
    from pyspark.sql import functions as F
    paths = [str(raw/s['name']) for s in shards]
    schemas = [spark.read.parquet(p).schema for p in paths]
    if not all(s == schemas[0] for s in schemas):
        raise ValueError('Schemas divergentes entre shards')
    frame = spark.read.parquet(*paths)
    if set(frame.columns) & set(METADATA):
        raise ValueError('Colunas da origem colidem com metadados Bronze')
    return frame.withColumn('_source_file', F.regexp_extract(F.input_file_name(),
                           r'(parquet_files/train/[^/]+\.parquet)$',1))


def build_temporal_bronze(root, spark, catalog, policy, *, fail_after_table=None):
    from pyspark.sql import functions as F
    from src.utils.paths import load_paths
    paths = load_paths(root)
    raw = paths['raw_dir']
    sources = source_fingerprints(raw,catalog)
    code = [Path(__file__), Path(__file__).parents[1]/'quality/reconcile_bronze.py',
            Path(__file__).with_name('build_bronze.py')]
    identity = {'format_version':1, 'policy':policy,
        'catalog':{'dictionary':catalog['dictionary'],'tables':catalog['tables']},
        'sources':sources,'spark_version':spark.version,
        'implementation_sha256':{p.name:sha256(p) for p in code}}
    digest = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    selection_id = digest[:24]
    namespace = paths['bronze_dir']/'expansion'
    namespace.mkdir(parents=True,exist_ok=True)
    destination = namespace/selection_id
    with _ingestion_lock(namespace):
        if destination.exists():
            return verify_committed(destination,identity), True
        started = time.monotonic()
        run_id = uuid.uuid4().hex
        stage = namespace/'.staging'/run_id
        stage.mkdir(parents=True,exist_ok=False)
        ingested = datetime.now(timezone.utc).isoformat()
        report = {'selection_id':selection_id,'identity_sha256':digest,'identity':identity,
            'run_id':run_id,'ingested_at_utc':ingested,'status':'running','tables':{}}
        def save():
            (stage/'_progress.json').write_text(json.dumps(report,indent=2)+'\n')
        save()
        cohort = None
        try:
            base = read_logical(spark,raw,catalog['tables']['train_base'])
            parsed = F.to_date(F.try_to_timestamp('date_decision', F.lit('yyyy-MM-dd')))
            invalid = base.where(F.col('case_id').isNull() | parsed.isNull()
                                 | (F.date_format(parsed,'yyyy-MM-dd') != F.col('date_decision'))).limit(1).count()
            base_stats = base.agg(F.count('*').alias('rows'),F.countDistinct('case_id').alias('cases')).first()
            if invalid or base_stats['rows'] != base_stats['cases']:
                raise ValueError('Base com data/chave inválida ou case_id duplicado')
            public = policy['windows']['public']
            selected_base = base.where((parsed >= F.lit(public['start_inclusive']).cast('date')) &
                                       (parsed < F.lit(public['end_exclusive']).cast('date')))
            cohort = selected_base.select('case_id').cache()
            report['population'] = {'full_base_cases':base_stats['cases'],'selected_cases':cohort.count(),'windows':{}}
            for name, window in policy['windows'].items():
                report['population']['windows'][name] = base.where(
                    (parsed >= F.lit(window['start_inclusive']).cast('date')) &
                    (parsed < F.lit(window['end_exclusive']).cast('date'))).count()
            report['population']['outside_public_cases'] = base_stats['cases']-report['population']['selected_cases']
            for name, shards in catalog['tables'].items():
                table_started = time.monotonic()
                expected = (selected_base if name=='train_base' else
                            read_logical(spark,raw,shards).join(cohort,'case_id','left_semi'))
                # Congelar a ordem antes do exceptAll posicional; nenhuma conversão de negócio.
                columns = expected.columns
                expected = expected.withColumn('_selection_id',F.lit(selection_id)).withColumn('_run_id',F.lit(run_id)).withColumn('_ingested_at_utc',F.lit(ingested))
                target = stage/'tables'/name
                expected.write.mode('errorifexists').parquet(str(target))
                actual = spark.read.parquet(str(target))
                comparison = compare_rows(expected,actual,columns+['_selection_id','_run_id','_ingested_at_utc'])
                input_rows, output_rows = expected.count(), actual.count()
                metadata_ok = actual.where(F.col('_source_file').isNull() | ~F.col('_source_file').isin([s['name'] for s in shards])).limit(1).count()==0
                if not comparison['success'] or input_rows != output_rows or not metadata_ok:
                    raise RuntimeError(f'Reconciliação Bronze falhou: {name}')
                report['tables'][name] = {'raw_selected_rows':input_rows,'bronze_rows':output_rows,
                    'business_columns':[c for c in columns if c!='_source_file'],
                    'schema':actual.schema.jsonValue(),'reconciliation':comparison,'source_files_valid':metadata_ok,
                    'duration_seconds':round(time.monotonic()-table_started,3)}
                save()
                print(f'{name}: {output_rows} linhas, valores e proveniência reconciliados',flush=True)
                if fail_after_table == name:
                    raise RuntimeError('Falha privada injetada')
            if source_fingerprints(raw,catalog) != sources:
                raise RuntimeError('RAW mudou durante o processamento')
            report['output_checksums'] = _output_checksums(stage)
            report['duration_seconds'] = round(time.monotonic()-started,3)
            report['status'] = 'passed'
            save()
            (stage/'_bronze.json').write_text(json.dumps(report,indent=2)+'\n')
            stage.rename(destination)
            return report, False
        except BaseException:
            report['status'] = 'failed'
            save()
            raise
        finally:
            if cohort is not None: cohort.unpersist()
