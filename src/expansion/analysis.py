"""E06: população integral, denominadores e SQL independente; somente agregados."""
from calendar import monthrange
import csv
from datetime import date
import json
from pathlib import Path
import time
import uuid
import yaml
from pyspark.sql import functions as F
from src.bronze.build_bronze import _ingestion_lock
from src.expansion.features import prefix
from src.expansion.gold import open_abt
from src.expansion.quality import compare_keyed,key_audit
from src.expansion.silver import open_silver
from src.expansion.storage import digest,finish_package,verify_package,pin_delta
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def load_policy(path):
    policy=yaml.safe_load(path.read_text())
    if (policy['version']!=1 or policy['scope']!='retrospective_full_public_population'
            or policy['labels']!='explicit_descriptive_access_no_model_selection'
            or policy['causal_or_operational_default_claim']!='forbidden'
            or policy['reserve_use']!='descriptive_only_no_fitted_preprocessing'
            or policy['start_inclusive']!='2020-01-01' or policy['end_exclusive']!='2020-10-01'):
        raise ValueError('Política de análise não suportada')
    return policy


def monthly_counts(frame):
    return frame.groupBy('MONTH').agg(F.count('*').alias('case_count'),
        F.count(F.when(F.col('target').isin(0,1),1)).alias('valid_label_count'),
        F.count(F.when(F.col('target')==1,1)).alias('target_1_count'),
        F.min('date_decision').alias('first_date'),F.max('date_decision').alias('last_date'))


def history_segment(c):
    return F.when(c==0,'no_history').when(c==1,'one_observation').when(c<=5,'two_to_five').otherwise('six_or_more')


def group_summary(frame,dimension,category):
    return frame.withColumn('category',category).groupBy('MONTH','category').agg(
        F.count('*').alias('case_count'),F.count(F.when(F.col('target').isin(0,1),1)).alias('valid_label_count'),
        F.count(F.when(F.col('target')==1,1)).alias('target_1_count')).withColumn('dimension',F.lit(dimension))


def _write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def build_analysis(repo,spark,silver_path,gold_path,policy_path,*,render=True):
    policy=load_policy(policy_path)
    silver,source=open_silver(repo,spark,silver_path)
    gold=verify_package(gold_path,'_gold.json')
    if gold['identity']['silver_manifest_sha256']!=sha256(silver_path/'_silver.json'):
        raise ValueError('Gold não corresponde à Silver')
    identity={'scope':'expansion_public_analysis_v1','gold_manifest_sha256':sha256(gold_path/'_gold.json'),
        'silver_manifest_sha256':sha256(silver_path/'_silver.json'),'policy_sha256':sha256(policy_path),
        'implementation_sha256':sha256(Path(__file__))}
    identifier=digest(identity)[:24];namespace=repo/'data/gold/expansion-analysis';namespace.mkdir(parents=True,exist_ok=True)
    dest=namespace/identifier
    with _ingestion_lock(namespace):
        if dest.exists():return verify_analysis(dest,identity),True
        stage=namespace/'.staging'/uuid.uuid4().hex;stage.mkdir(parents=True)
        start=time.monotonic()
        dev=open_abt(repo,spark,gold_path,'development',include_labels=True).withColumn('period',F.lit('development'))
        evaluation=open_abt(repo,spark,gold_path,'evaluation',include_labels=True,allow_evaluation_labels=True).withColumn('period',F.lit('evaluation'))
        public=dev.unionByName(evaluation).cache();key_audit(public,['case_id'])
        public.createOrReplaceTempView('public_analysis_abt');source['train_base'].createOrReplaceTempView('public_analysis_base')
        manifest={'id':identifier,'identity':identity,'identity_sha256':digest(identity),'status':'running',
            'tables':{},'proofs':{},'gold_id':gold['id'],'silver_id':silver['id'],'ml_ready':False,
            'interpretation':'retrospective_descriptive_no_maturation_or_operational_default_claim',
            'label_use':'reserve_labels_used_only_for_descriptive_analysis_no_model_fit_or_feature_selection'}
        def save_table(name,frame,key):
            frame=frame.cache()
            key_audit(frame,key)
            path=stage/'tables'/name;frame.write.format('delta').save(str(path))
            actual=spark.read.format('delta').load(str(path));q=key_audit(actual,key)
            proof=compare_keyed(frame,actual,key)
            if not proof['success']:raise ValueError('Readback analítico divergiu: '+name)
            manifest['tables'][name]=pin_delta(spark,path,str((dest/'tables'/name).relative_to(repo)),q['rows'])
            manifest['proofs'][name+'_readback']=proof
            frame.unpersist()
            return actual
        try:
            counts=monthly_counts(public)
            sql=spark.sql('''SELECT MONTH, COUNT(*) AS case_count,
                COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count,
                COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count,
                MIN(date_decision) AS first_date, MAX(date_decision) AS last_date
                FROM public_analysis_base GROUP BY MONTH''')
            proof=compare_keyed(sql,counts,['MONTH'])
            if not proof['success']:raise ValueError('Mensal diverge da base Silver')
            manifest['proofs']['monthly_silver_sql']=proof
            calendar=spark.createDataFrame([(202000+m,) for m in range(1,10)],'MONTH long')
            monthly=calendar.join(counts,'MONTH','left').fillna(0,subset=['case_count','valid_label_count','target_1_count'])
            monthly=monthly.withColumn('target_1_rate',F.when(F.col('valid_label_count')>0,F.col('target_1_count')/F.col('valid_label_count')))
            monthly=save_table('monthly',monthly,['MONTH'])
            coverage_parts=[]
            for name,frame in source.items():
                if name=='train_base':continue
                p=prefix(name);hist_raw=public.groupBy('MONTH').agg(
                    F.count(F.when(F.col(p+'has_source'),1)).alias('covered_cases'),F.sum(p+'observation_count').alias('observations'),
                    F.count('*').alias('case_count'))
                hist=calendar.join(hist_raw,'MONTH','left').fillna(0,['covered_cases','observations','case_count'])
                frame.select('case_id').createOrReplaceTempView('coverage_source')
                oracle=spark.sql('''SELECT b.MONTH,COUNT(DISTINCT s.case_id) AS covered_cases,COUNT(*) AS observations
                    FROM coverage_source s JOIN public_analysis_base b ON s.case_id=b.case_id GROUP BY b.MONTH''')
                expected=monthly.select('MONTH','case_count').join(oracle,'MONTH','left').fillna(0,['covered_cases','observations'])
                proof=compare_keyed(expected,hist,['MONTH'])
                if not proof['success']:raise ValueError('Cobertura diverge da origem: '+name)
                manifest['proofs']['coverage_'+name]=proof
                coverage_parts.append(hist.withColumn('source_table',F.lit(name)))
            coverage=coverage_parts[0]
            for part in coverage_parts[1:]:coverage=coverage.unionByName(part)
            coverage=coverage.withColumn('coverage_rate',F.when(F.col('case_count')>0,F.col('covered_cases')/F.col('case_count')))
            coverage=save_table('coverage',coverage,['MONTH','source_table'])
            feature_names=[c for c in public.columns if c not in {'case_id','date_decision','MONTH','WEEK_NUM','target','period'}]
            agg=public.groupBy('MONTH').agg(F.count('*').alias('case_count'),*[F.count(c).alias('f'+str(i)) for i,c in enumerate(feature_names)])
            expressions=[f'COUNT(`{c}`) AS f{i}' for i,c in enumerate(feature_names)]
            oracle=spark.sql('SELECT MONTH,COUNT(*) AS case_count,'+', '.join(expressions)+' FROM public_analysis_abt GROUP BY MONTH')
            proof=compare_keyed(oracle,agg,['MONTH'])
            if not proof['success']:raise ValueError('Completude diverge do SQL')
            manifest['proofs']['missingness_sql']=proof
            agg=calendar.join(agg,'MONTH','left').fillna(0)
            # Até nove linhas largas agregadas são coletadas; nenhum caso individual sai do Spark.
            missing_rows=[]
            for row in agg.collect():
                for i,name in enumerate(feature_names):missing_rows.append((row.MONTH,name,row.case_count,row['f'+str(i)],row.case_count-row['f'+str(i)]))
            missing=spark.createDataFrame(missing_rows,'MONTH long,feature string,case_count long,non_null_count long,null_count long')
            missing=save_table('missingness',missing,['MONTH','feature'])
            composition=group_summary(public,'previous_application_history',history_segment(F.col(policy['history_source'])))
            for dimension,column in policy['categories'].items():
                composition=composition.unionByName(group_summary(public,dimension,F.when(F.col(column).isNull(),'__NULL__').otherwise(F.concat(F.lit('VALUE:'),F.col(column)))))
            for dimension,column in [('previous_application_history',None),*policy['categories'].items()]:
                expression=("CASE WHEN applprev_1__observation_count=0 THEN 'no_history' WHEN applprev_1__observation_count=1 THEN 'one_observation' WHEN applprev_1__observation_count<=5 THEN 'two_to_five' ELSE 'six_or_more' END" if column is None else f"CASE WHEN `{column}` IS NULL THEN '__NULL__' ELSE CONCAT('VALUE:',`{column}`) END")
                sql=spark.sql(f'''SELECT MONTH,{expression} AS category,COUNT(*) AS case_count,
                    COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count,
                    COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count FROM public_analysis_abt GROUP BY MONTH,{expression}''')
                proof=compare_keyed(sql,composition.where(F.col('dimension')==dimension).drop('dimension'),['MONTH','category'])
                if not proof['success']:raise ValueError('Composição diverge do SQL')
                manifest['proofs']['composition_'+dimension]=proof
            composition=composition.withColumn('small_group',F.col('case_count')<policy['small_group_min_cases']).withColumn('few_target_1',F.col('target_1_count')<policy['small_group_min_target_1'])
            composition=save_table('composition',composition,['MONTH','dimension','category'])
            expressions=[F.count('*').alias('case_count'),F.count(F.when(F.col('target').isin(0,1),1)).alias('valid_label_count'),F.count(F.when(F.col('target')==1,1)).alias('target_1_count')]
            for i,c in enumerate(policy['selected_numeric']):expressions += [F.count(c).alias(f'numeric_{i}_non_null'),F.avg(c).alias(f'numeric_{i}_mean')]
            periods=public.groupBy('period').agg(*expressions)
            sql_expr=['COUNT(*) AS case_count','COUNT(CASE WHEN target IN (0,1) THEN 1 END) AS valid_label_count','COUNT(CASE WHEN target=1 THEN 1 END) AS target_1_count']
            for i,c in enumerate(policy['selected_numeric']):sql_expr += [f'COUNT(`{c}`) AS numeric_{i}_non_null',f'AVG(`{c}`) AS numeric_{i}_mean']
            proof=compare_keyed(spark.sql('SELECT period,'+', '.join(sql_expr)+' FROM public_analysis_abt GROUP BY period'),periods,['period'],numeric_tolerance=(1e-8,1e-10))
            if not proof['success']:raise ValueError('Comparação entre períodos diverge do SQL')
            manifest['proofs']['periods_sql']=proof
            periods=save_table('period_compare',periods,['period'])
            report_rows={name:[r.asDict() for r in table.orderBy(*keys).collect()] for name,table,keys in
                [('monthly',monthly,['MONTH']),('coverage',coverage,['MONTH','source_table']),('missingness',missing,['MONTH','feature']),
                 ('composition',composition,['MONTH','dimension','category']),('period_compare',periods,['period'])]}
            report={'policy':policy,'rows':report_rows,'status':'passed','population_cases':sum(r['case_count'] for r in report_rows['monthly']),
                    'gold_id':gold['id'],'silver_id':silver['id']}
            for row in report_rows['monthly']:
                month=row['MONTH'];year,m=divmod(month,100)
                row['empty_month']=row['case_count']==0
                row['observed_partial_month']=bool(row['case_count'] and (row['first_date']!=date(year,m,1) or row['last_date']!=date(year,m,monthrange(year,m)[1])))
            artifacts=stage/'report';artifacts.mkdir()
            (artifacts/'report.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
            for name,rows in report_rows.items():_write_csv(artifacts/(name+'.csv'),rows)
            if render:render_report(artifacts,report)
            manifest['report_files']={p.name:sha256(p) for p in artifacts.iterdir() if p.is_file()}
            manifest.update(duration_seconds=round(time.monotonic()-start,3),population_cases=report['population_cases'])
            result=finish_package(stage,dest,manifest,'_analysis.json')
            return result,False
        except BaseException as exc:
            manifest.update(status='failed',error_type=type(exc).__name__);atomic_json(stage/'_progress.json',manifest);raise
        finally:public.unpersist()


def render_report(path,report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    monthly=report['rows']['monthly'];labels=[str(r['MONTH']) for r in monthly]
    fig,axes=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    axes[0].bar(labels,[r['case_count'] for r in monthly],color='#246c91');axes[0].set_ylabel('Casos de crédito')
    axes[1].plot(labels,[100*r['target_1_rate'] if r['target_1_rate'] is not None else float('nan') for r in monthly],marker='o',color='#a15c31')
    axes[1].set_ylabel('Target 1 / rótulos válidos (%)');axes[1].set_xlabel('Mês da decisão')
    fig.suptitle('Janeiro–setembro/2020: descrição retrospectiva; maturação não comprovada')
    for fmt in ('png','svg'):fig.savefig(path/('monthly.'+fmt),dpi=150)
    plt.close(fig)
    sources=sorted({r['source_table'] for r in report['rows']['coverage']})
    lookup={(r['source_table'],r['MONTH']):r['coverage_rate'] for r in report['rows']['coverage']}
    fig,ax=plt.subplots(figsize=(11,7),layout='constrained')
    values=[[100*(lookup.get((s,r['MONTH'])) or 0) for r in monthly] for s in sources]
    image=ax.imshow(values,vmin=0,vmax=100,aspect='auto',cmap='Blues')
    ax.set_yticks(range(len(sources)),[s.removeprefix('train_') for s in sources]);ax.set_xticks(range(9),labels)
    ax.set_title('Cobertura: casos com observações / casos do mês');fig.colorbar(image,ax=ax,label='%')
    for fmt in ('png','svg'):fig.savefig(path/('coverage.'+fmt),dpi=150)
    plt.close(fig)


def verify_analysis(root,identity=None):
    manifest=verify_package(root,'_analysis.json',identity)
    files={p.name:sha256(p) for p in (root/'report').iterdir() if p.is_file()}
    if manifest.get('report_files')!=files:raise ValueError('Relatório/gráficos alterados')
    return manifest
