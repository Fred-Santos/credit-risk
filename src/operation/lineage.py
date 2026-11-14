"""Inventário por publicação explícita; nenhuma inferência a partir de CURRENT."""
import json
from pathlib import Path
from src.gold.model import ABT_SCHEMA, MONTH_SCHEMA
from src.silver.initial_delta import TABLES
from src.quality.event_contracts import digest
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import local, atomic_json
from src.object_store.mirror import verify_mirror
from src.object_store.publication import open_object_publication

MODEL_SHA='e046e334dda8396314db4c64f7a394ddcae5994bf9b96289dd2347243bf99d32'


def column_lineage(model_sha):
    if model_sha!=MODEL_SHA:raise ValueError('Modelo Gold sem mapeamento de lineage aprovado')
    def rule(sources,transform):return {'sources':sources.split(), 'transform':transform}
    base={c:rule('silver.credit_cases.'+c,'projection') for c in ('case_id','date_decision','MONTH','WEEK_NUM','target')}
    base.update({
        'static_annuity':rule('silver.credit_static.annuity_780A','left_join_case_id'),
        'has_static':rule('silver.credit_cases.case_id silver.credit_static.case_id','left_join_presence_false_when_missing'),
        'has_previous_applications':rule('silver.previous_applications.case_id silver.previous_applications.num_group1','observation_count_greater_than_zero'),
        'previous_application_count':rule('silver.previous_applications.case_id silver.previous_applications.num_group1','count_observations_per_case_zero_when_missing'),
        'previous_amount_non_null_count':rule('silver.previous_applications.case_id silver.previous_applications.credamount_590A','count_non_null_amounts_per_case_zero_when_missing'),
        'case_source_revision':rule('silver.credit_cases._source_revision','projection'),
        'static_source_revision':rule('silver.credit_static._source_revision','left_join_case_id'),
        'previous_max_source_revision':rule('silver.previous_applications._source_revision','max_per_case'),
        'has_revised_source':rule('silver.credit_cases._source_revision silver.credit_static._source_revision silver.previous_applications._source_revision','any_revision_greater_than_one_null_as_zero'),
        '_abt_contract_version':{'sources':[],'transform':'constant_int_1'}})
    for suffix,transform in [('sum','ordered_double_sum_null_when_no_non_null'),('mean','ordered_sum_divided_by_non_null_count'),('min','min_null_when_no_non_null'),('max','max_null_when_no_non_null')]:
        base['previous_amount_'+suffix]=rule('silver.previous_applications.case_id silver.previous_applications.num_group1 silver.previous_applications.credamount_590A',transform)
    month={
        'MONTH':rule('gold.abt.MONTH','group_by_month'),
        'case_count':rule('gold.abt.MONTH gold.abt.case_id','count_rows'),
        'valid_label_count':rule('gold.abt.MONTH gold.abt.target','count_target_in_0_1'),
        'target_1_count':rule('gold.abt.MONTH gold.abt.target','count_target_equal_1'),
        'target_1_rate':rule('gold.abt.MONTH gold.abt.target','count_target_1_divided_by_valid_labels_null_if_zero')}
    for name,source,transform in [
        ('static_covered_count','has_static','count_true'),('static_coverage_rate','has_static','count_true_divided_by_case_count'),
        ('history_covered_count','has_previous_applications','count_true'),('history_coverage_rate','has_previous_applications','count_true_divided_by_case_count'),
        ('history_row_count','previous_application_count','sum'),('history_amount_non_null_count','previous_amount_non_null_count','sum')]:
        month[name]=rule('gold.abt.MONTH gold.abt.'+source,transform)
    if set(base)!=set(ABT_SCHEMA) or set(month)!=set(MONTH_SCHEMA):raise ValueError('Mapeamento incompleto')
    return {'model_sha256':model_sha,'kind':'explicit_reviewed_mapping_not_sql_parser',
        'gold.abt':base,'gold.monthly_metrics':month,'join_key':'case_id',
        'history_grain':['case_id','num_group1'],'temporal_scope':'retrospective_not_point_in_time'}


def validate_links(operation, run, manifest):
    if operation.get('status')!='passed' or run.get('status')!='passed':raise ValueError('Operação/run não aprovados')
    result=operation['result'];options=operation['options']
    if (result['run_id']!=run['run_id'] or result['publication_id']!=run['publication_id']
        or manifest['publication_id']!=run['publication_id']
        or not any(a['run_id']==run['run_id'] and a['status']=='passed' for a in operation['attempts'])
        or any(options[k]!=run[k2] for k,k2 in [('sample','selection_id'),('mode','mode'),('batch','batch')])):
        raise ValueError('Vínculo operação/run/publicação divergente')
    identity=manifest['identity']
    if (identity['scope']!='operational_analytics_v1' or identity['selection_id']!=run['selection_id']
        or identity['source_versions']!=run['source_versions']
        or identity['state_identity']['fingerprints']!=run['fingerprints']):raise ValueError('Identidade de origem divergente')
    return column_lineage(manifest['provenance']['src/gold/model.py']['sha256'])


def audit(ctx, client, spark, operation_relative):
    repo=ctx.repo_root;op_path=local(repo,operation_relative);op_bytes=op_path.read_bytes();operation=json.loads(op_bytes)
    # O supervisor registra paths absolutos locais; confinar antes de ler.
    run_path=Path(operation['result']['report']).resolve()
    if not run_path.is_relative_to(repo):raise ValueError('Relatório fora do repositório')
    run_path=local(repo,run_path.relative_to(repo).as_posix());run_bytes=run_path.read_bytes();run=json.loads(run_bytes)
    registry=client.config['prefix']+'/operational-publications/'+run['selection_id']
    if registry!=run['registry']:raise ValueError('Registry operacional incompatível')
    with open_object_publication(client,registry,spark,run['publication_id']) as (manifest,frames):
        columns=validate_links(operation,run,manifest)
        state_identity=manifest['identity']['state_identity'];mirror_ref=state_identity['mirror']
        if mirror_ref not in manifest['references'] or client.checksum(mirror_ref['key'])!=mirror_ref['sha256']:
            raise ValueError('Espelho não vinculado à publicação')
        mirror=client.json(mirror_ref['key']);verify_mirror(client,mirror)
        if mirror['identity']['selection_id']!=run['selection_id']:raise ValueError('Coorte do espelho divergente')
        def one(predicate):
            found=[(name,entry) for name,entry in mirror['files'].items() if predicate(name,entry)]
            if len(found)!=1:raise ValueError('Referência de origem ausente ou ambígua')
            name,entry=found[0];return name,entry,client.json(entry['key'])
        selection_path,selection_ref,selection=one(lambda n,e:n.endswith('/_selection.json'))
        bronze_path,bronze_ref,bronze=one(lambda n,e:n.endswith('/_READY.json'))
        source_path,source_ref,source=one(lambda n,e:e['sha256']==mirror['identity']['f04_report_sha256'])
        if (mirror['identity']['bronze_gate_sha256']!=bronze_ref['sha256']
            or bronze['input']['sample_manifest_sha256']!=selection_ref['sha256']
            or selection['selection_id']!=run['selection_id'] or bronze['status']!='passed'
            or bronze['input']['selection_id']!=run['selection_id'] or source['status']!='passed'
            or source['identity']['binding']!=state_identity['source_binding']
            or source['stream_id']!=state_identity['source_stream_id']):raise ValueError('Origem do stream divergente')
        packets={p['batch_id']:p for p in source['generation']['publications']};batches=[]
        for observed in run['batches']:
            key=run['state_prefix']+'/applied/'+observed['batch_id']+'.json'
            reference={'key':key,'sha256':client.checksum(key)}
            if reference not in manifest['references']:raise ValueError('Recibo fora das referências aprovadas')
            receipt=client.json(key);packet=packets[observed['batch_id']]
            if receipt['packet_sha256']!=observed['packet_sha256'] or receipt['packet_sha256']!=packet['packet_sha256']:
                raise ValueError('Pacote/recibo divergente')
            batches.append({'batch_id':observed['batch_id'],'packet_sha256':receipt['packet_sha256'],
                'receipt':reference,'original_versions_after':receipt['versions_after'],
                'observed_versions_after':observed['versions_after'],
                'landing_prefix':source['events_root']+'/'+observed['batch_id']})
        if (len({b['batch_id'] for b in batches})!=len(batches)
            or {b['receipt']['key'] for b in batches}!={r['key'] for r in manifest['references'] if r['key'].startswith(run['state_prefix']+'/applied/')}):
            raise ValueError('Inventário de lotes incompleto ou duplicado')
        inventory={name:{**entry,'logical_table':name,'files_count':len(entry['files'])} for name,entry in manifest['tables'].items()}
        for table,rules in [(name,columns[name]) for name in ('gold.abt','gold.monthly_metrics')]:
            for rule in rules.values():
                for origin in rule['sources']:
                    layer,name,column=origin.split('.',2)
                    if column not in inventory[layer+'.'+name]['schema']:raise ValueError('Coluna de origem ausente')
        creation_attempts=[]
        for path in sorted((repo/'artifacts/f08/attempts').glob('*.json')):
            record=json.loads(path.read_text())
            if record.get('publication_id')==manifest['publication_id'] and record.get('status')=='passed' and record.get('reused') is False:
                creation_attempts.append({'run_id':record['run_id'],'path':path.relative_to(repo).as_posix(),'sha256':sha256(path)})
        table_lineage=[];upstream_tables={}
        selection_root=selection_path.rsplit('/',1)[0];bronze_root=bronze_path.rsplit('/',1)[0]
        for source_name,silver_name in TABLES.items():
            raw_files={name:entry for name,entry in mirror['identity']['raw'].items()
                if Path(name).name==source_name+'.parquet' or Path(name).name.startswith(source_name+'_')}
            if not raw_files:raise ValueError('Tabela RAW sem arquivos vinculados')
            nodes=['raw.'+source_name,'selection.'+source_name,'bronze.'+source_name,'landing.'+source_name,
                   'working.'+silver_name,'silver.'+silver_name]
            mirrored_raw={n:e for n,e in mirror['files'].items() if any(n.endswith('/'+raw_name) and e['sha256']==raw_entry['sha256'] for raw_name,raw_entry in raw_files.items())}
            if len(mirrored_raw)!=len(raw_files):raise ValueError('Arquivos RAW sem correspondência no espelho')
            upstream_tables[nodes[0]]={'files':raw_files,'mirrored_files':mirrored_raw,'scope':'original source edition before cohort selection'}
            for node,prefix in [(nodes[1],selection_root+'/parquet_files/train/'+source_name+'/'),(nodes[2],bronze_root+'/'+source_name+'/')]:
                files={n:e for n,e in mirror['files'].items() if n.startswith(prefix)}
                if not files:raise ValueError('Tabela de entrada sem inventário')
                upstream_tables[node]={'original_prefix':prefix,'files':files}
            upstream_tables[nodes[3]]={'batches':[{'batch_id':b['batch_id'],'original_prefix':b['landing_prefix']+'/'+source_name} for b in batches],
                'scope':'simulated arrivals and revisions from approved F04'}
            upstream_tables[nodes[4]]={'uri':client.uri(run['state_prefix']+'/'+silver_name),
                'version_at_publication':run['source_versions'][silver_name], 'scope':'mutable working state; historical inventory does not require latest state unchanged'}
            for left,right,transform in zip(nodes,nodes[1:],['deterministic_case_selection','preserve_values_add_provenance','simulate_delivery_and_revision',
                    'revision_precedence_and_merge','controlled_silver_contract_v2']):
                table_lineage.append({'from':left,'to':right,'transform':transform})
            table_lineage.append({'from':nodes[-1],'to':'gold.abt','transform':'aggregate_history_before_left_joins'})
        table_lineage.append({'from':'gold.abt','to':'gold.monthly_metrics','transform':'monthly_sql'})
        identity={'operation_id':operation['operation_id'],'operation_sha256':sha256(op_path),
            'run_id':run['run_id'],'run_sha256':sha256(run_path),'publication_id':manifest['publication_id'],
            'manifest_sha256':client.checksum(registry+'/manifests/'+manifest['publication_id']+'.json'),
            'auditor_sha256':sha256(repo/'src/operation/lineage.py')}
        report={'format_version':1,'status':'passed','audit_run_id':ctx.run_id,'inventory_id':digest(identity)[:24],
            'identity':identity,'publication_creation_attempts':creation_attempts,
            'creation_attempt_scope':'observed local passed attempt logs, content-hashed; not a field signed into the S3 manifest',
            'manifest_reference':{'key':registry+'/manifests/'+manifest['publication_id']+'.json','sha256':identity['manifest_sha256']},
            'retention':manifest['retention'],'upstream_tables':upstream_tables,'table_lineage':table_lineage,
            'selection_id':run['selection_id'],'state_prefix':run['state_prefix'],
            'source_versions':run['source_versions'],'mirror':{**mirror_ref,'mirror_id':mirror['mirror_id']},
            'inputs':{'raw':mirror['identity']['raw'],'selection':{'path':selection_path,'reference':selection_ref,'first_run_id':selection['first_run_id'],'case_count':selection['case_count'],'counts':selection['counts'],'case_set_sha256':selection['case_set_sha256']},
                'bronze':{'path':bronze_path,'reference':bronze_ref,'verified_by_run_id':bronze['verified_by_run_id'],'counts':bronze['counts']},
                'f04':{'path':source_path,'reference':source_ref,'run_id':source['run_id'],'stream_id':source['stream_id'],'final_versions':source['final_versions']},
                'files':mirror['files']},'batches':batches,'tables':inventory,'column_lineage':columns,
            'consumers':[{'consumer':'gold.abt','inputs':['silver.credit_cases','silver.credit_static','silver.previous_applications'],'kind':'published_transform'},
                {'consumer':'gold.monthly_metrics','inputs':['gold.abt'],'kind':'published_transform'},
                {'consumer':'inventory_auditor','run_id':ctx.run_id,'inputs':sorted(frames),'kind':'verified_delta_read'}],
            'consumer_scope':'known dependencies and this verified reader; not a global access log; F07 consumes its original filesystem F06 publications',
            'provenance':manifest['provenance']}
    if op_path.read_bytes()!=op_bytes or run_path.read_bytes()!=run_bytes:raise RuntimeError('Relatórios mudaram durante auditoria')
    output=repo/'artifacts/f09/inventory'/report['inventory_id']/(ctx.run_id+'.json')
    atomic_json(output,report)
    return {'status':'passed','inventory_id':report['inventory_id'],'report':str(output),'tables':len(inventory),'batches':len(batches)}
