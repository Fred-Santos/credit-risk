"""F07: consumir três publicações explícitas sem modificar dados ou CURRENT."""
import argparse
from datetime import datetime,timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import time

from src.analytics.queries import load_analysis_policy,monthly_analysis,population_summary,history_segments,compare_publications
from src.analytics.report import canonical_json,render_bundle
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import archive_provenance,atomic_json,open_publication,verify_manifest
from src.quality.event_contracts import digest
from src.silver.initial_delta import _files
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

CODE=('src/pipelines/run_analysis.py','src/analytics/queries.py','src/analytics/report.py',
      'src/publication/protocol.py','src/quality/reconcile_bronze.py','src/utils/spark.py',
      'src/utils/run_context.py','src/utils/paths.py','scripts/analysis.sh')
CONFIG=('configs/analysis_policy_v1.yaml','configs/contracts/gold_v1.yaml','configs/spark.yaml',
        'configs/paths.yaml','requirements.lock','requirements.analysis.lock')


def require_triplet(repo,registry,manifests,selection):
    if len({m['publication_id'] for m in manifests.values()})!=3:
        raise ValueError('Forneça baseline, correção e final distintos')
    for label,m in manifests.items():
        if m['identity']['scope']!='analytics_v1' or m['identity']['selection_id']!=selection:
            raise ValueError('Publicações analíticas devem pertencer à mesma seleção')
        if m['identity']['gold_contract_sha256']!=manifests['final']['identity']['gold_contract_sha256']:
            raise ValueError('Comparações exigem o mesmo contrato Gold')
    for child,parent in (('corrected','baseline'),('final','corrected')):
        p=registry/'manifests'/(manifests[parent]['publication_id']+'.json')
        expected={'manifest':p.relative_to(repo).as_posix(),'sha256':sha256(p)}
        if manifests[child]['identity']['parent_analytics']!=expected:
            raise ValueError('Ordem/linhagem das três publicações não corresponde à comparação')


def collect_view(frames,policy):
    from pyspark import StorageLevel
    abt=frames['gold.abt'].persist(StorageLevel.MEMORY_AND_DISK)
    try:
        population=population_summary(abt)
        monthly,monthly_proof=monthly_analysis(abt,frames['gold.monthly_metrics'],policy)
        segments,segment_proof=history_segments(abt,policy)
        for field in ('case_count','valid_label_count','target_1_count'):
            if sum(r[field] for r in monthly)!=population[field] or sum(r[field] for r in segments)!=population[field]:
                raise ValueError('Totais de meses/segmentos não reconciliam com a população')
        return {'population':population,'monthly':monthly,'segments':segments,
                'checks':{'monthly_vs_independent_sql':monthly_proof,'segments_vs_independent_sql':segment_proof,
                          'population_reconciliation':True}}
    finally:
        abt.unpersist()


def run_analysis(ctx,spark,*,selection,publication,baseline,corrected):
    started=time.perf_counter()
    if not re.fullmatch(r'[0-9a-f]{24}',selection):
        raise ValueError('selection_id inválido')
    policy=load_analysis_policy(ctx.repo_root/CONFIG[0])
    fingerprints={p:sha256(ctx.repo_root/p) for p in CODE+CONFIG}
    registry=ctx.repo_root/'artifacts/publications'/selection/'analytics'
    ids={'baseline':baseline,'corrected':corrected,'final':publication}
    current_path=registry/'_CURRENT.json'
    current_before=current_path.read_bytes() if current_path.exists() else None
    manifest_files={label:registry/'manifests'/(value+'.json') for label,value in ids.items()}
    runtime={'python':version_python(),'spark':spark.version,'matplotlib':version('matplotlib'),
             'numpy':version('numpy')}
    output=None
    status={'run_id':ctx.run_id,'selection_id':selection,'status':'running'}
    try:
        with open_publication(ctx.repo_root,registry,spark,publication_id=publication) as (final,final_frames):
            manifests={'final':final}
            frames={'final':final_frames}
            for label in ('baseline','corrected'):
                manifests[label],frames[label]=verify_manifest(ctx.repo_root,registry,ids[label],spark)
            require_triplet(ctx.repo_root,registry,manifests,selection)
            input_hashes={label:sha256(p) for label,p in manifest_files.items()}
            identity={'scope':'retrospective_analysis_v1','selection_id':selection,
                'publications':{label:{'id':ids[label],'manifest_sha256':input_hashes[label]} for label in ids},
                'code_and_configuration':fingerprints,'runtime':runtime}
            analysis_id=digest(identity)[:24]
            output=ctx.repo_root/'artifacts/analysis'/selection/analysis_id/ctx.run_id
            output.mkdir(parents=True,exist_ok=False)
            archive=archive_provenance(ctx.repo_root,output,fingerprints)
            status.update(analysis_id=analysis_id,identity=identity,provenance=archive)
            views={label:collect_view(frames[label],policy) for label in ids}
            comparisons={'correction':compare_publications(frames['baseline'],frames['corrected'],kind='correction',policy=policy),
                'late_arrival':compare_publications(frames['corrected'],frames['final'],kind='late_arrival',policy=policy)}
            payload={'format_version':1,'selection_id':selection,'publication_ids':ids,'views':views,'comparisons':comparisons,
                'limitations':{'retrospective_only':True,'label_maturity_audited':False,'causal_claim':False,
                    'operational_portfolio_rate':False,'sample_design_for_population_inference':False}}
            metadata={**status,'publications':{label:{'publication_id':ids[label],
                'manifest':manifest_files[label].relative_to(ctx.repo_root).as_posix(),'manifest_sha256':input_hashes[label],
                'tables':{n:{k:t[k] for k in ('path','delta_table_id','version','rows')} for n,t in m['tables'].items()}}
                for label,m in manifests.items()},'runtime':runtime}
            render_bundle(output,payload,metadata)
            for label,m in manifests.items():
                if sha256(manifest_files[label])!=input_hashes[label]:
                    raise RuntimeError('Manifesto de entrada mudou durante análise')
                for entry in m['tables'].values():
                    if _files(ctx.repo_root/entry['path'])!=entry['files']:
                        raise RuntimeError('Dados de entrada mudaram durante análise')
        if (current_path.read_bytes() if current_path.exists() else None)!=current_before:
            raise RuntimeError('CURRENT mudou durante análise')
        if any(sha256(ctx.repo_root/p)!=h for p,h in fingerprints.items()):
            raise RuntimeError('Código/configuração mudou durante análise')
        status.update(status='passed',duration_seconds=round(time.perf_counter()-started,3),
            finished_at_utc=datetime.now(timezone.utc).isoformat(),
            output=output.relative_to(ctx.repo_root).as_posix(),source_files_preserved=True,current_preserved=True,
            semantic_sha256=sha256(output/'semantic.json'))
        metadata.update(status)
        atomic_json(output/'metadata.json',metadata)
        outputs={p.relative_to(output).as_posix():sha256(p) for p in sorted(output.rglob('*')) if p.is_file()}
        atomic_json(output/'_SUCCESS.json',{'status':'passed','run_id':ctx.run_id,'analysis_id':analysis_id,
            'semantic_sha256':status['semantic_sha256'],'outputs':outputs})
    except BaseException as error:
        status.update(status='failed',error_type=type(error).__name__,error=str(error))
        atomic_json(ctx.repo_root/'artifacts/f07/runs'/(ctx.run_id+'.json'),status)
        raise
    atomic_json(ctx.repo_root/'artifacts/f07/runs'/(ctx.run_id+'.json'),status)
    return status


def version_python():
    import platform
    return platform.python_version()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',required=True)
    parser.add_argument('--publication',required=True,help='Publicação analítica final explícita; não usa CURRENT')
    parser.add_argument('--baseline',required=True)
    parser.add_argument('--corrected',required=True)
    args=parser.parse_args()
    ctx=RunContext.create(Path(__file__).resolve().parents[2])
    spark=create_spark_session(ctx.repo_root,app_name='f07-analysis',delta=True)
    spark.conf.set('spark.databricks.delta.snapshotPartitions',spark.conf.get('spark.sql.shuffle.partitions'))
    try:
        result=run_analysis(ctx,spark,selection=args.sample,publication=args.publication,baseline=args.baseline,corrected=args.corrected)
    finally:
        spark.stop()
    print(json.dumps(result))


if __name__=='__main__':
    main()
