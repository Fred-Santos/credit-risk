"""Resumo pontual: história local e publicação observada, sem alterar CURRENT."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import yaml
from src.publication.protocol import local, atomic_json
from src.quality.event_contracts import digest


def timestamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Horário sem timezone')
    return result.astimezone(timezone.utc)


def alert_profiles(repo):
    path=repo/'configs/operational_alerts_v1.yaml';policy=yaml.safe_load(path.read_text())
    if (policy['version']!=1 or policy['scope']!='local_observational_not_sla'
        or not all(isinstance(policy[k],(int,float)) and math.isfinite(policy[k]) and policy[k]>=1 for k in ('duration_factor','rss_factor'))):
        raise ValueError('Política de alertas inválida')
    profiles=[]
    for item in policy['baselines']:
        raw=local(repo,item['report']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Baseline de alerta alterada')
        baseline=json.loads(raw);seconds=baseline['timing']['total_seconds'];rss=baseline['resources']['peak_process_tree_rss_bytes']
        if baseline['status']!='passed' or not math.isfinite(seconds) or seconds<=0 or rss<=0:raise ValueError('Baseline não aprovada')
        options=baseline['options']
        key={k:options[k] for k in ('sample','mode','batch')}
        if any(p['match']==key for p in profiles):raise ValueError('Baseline duplicada')
        profiles.append({'match':key,'duration_warning_seconds':seconds*policy['duration_factor'],
            'rss_warning_bytes':int(rss*policy['rss_factor']),'baseline':item})
    return {'status':'validated','policy_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':policy['scope'],
            'duration_factor':policy['duration_factor'],'rss_factor':policy['rss_factor'],'profiles':profiles}


def load_history(repo, sample):
    operations=[];diagnostics=[]
    for path in sorted((repo/'artifacts/f09/operations').glob('*.json')):
        try:
            raw=path.read_bytes();record=json.loads(raw)
            if record['options']['sample']!=sample:continue
            timestamp(record['started_at_utc'])
            if record['status'] not in ('running','retry_wait','passed','failed','cancelled'):raise ValueError('Estado desconhecido')
            if not isinstance(record['operation_id'],str) or not isinstance(record['attempts'],list) or any(not isinstance(a,dict) for a in record['attempts']):
                raise ValueError('Identidade/tentativas inválidas')
            for section,key in [('timing','total_seconds'),('resources','peak_process_tree_rss_bytes')]:
                metrics=record.get(section,{})
                if not isinstance(metrics,dict):raise ValueError('Seção de métricas inválida')
                value=metrics.get(key)
                if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<0):
                    raise ValueError('Métrica inválida no relatório')
            operations.append({**record,'report':path.relative_to(repo).as_posix(),'report_sha256':hashlib.sha256(raw).hexdigest()})
        except (OSError,ValueError,TypeError,KeyError) as error:
            diagnostics.append({'report':path.relative_to(repo).as_posix(),'error_type':type(error).__name__,'error':str(error)})
    operations.sort(key=lambda r:(timestamp(r['started_at_utc']),r['operation_id']),reverse=True)
    return operations,diagnostics


def validate_snapshot(snapshot, sample):
    pointer=snapshot['pointer'];raw=snapshot['manifest_json'];manifest=json.loads(raw)
    if hashlib.sha256(raw.encode()).hexdigest()!=pointer['manifest_sha256']:raise ValueError('Manifesto/cache diverge do ponteiro')
    if (snapshot.get('format_version')!=1 or manifest.get('format_version')!=1
        or manifest['identity'].get('scope')!='operational_analytics_v1' or pointer['publication_id']!=manifest['publication_id'] or manifest['identity']['selection_id']!=sample
        or digest(manifest['identity'])[:24]!=manifest['publication_id'] or manifest['status']!='passed'
        or set(manifest['tables'])!={'silver.credit_cases','silver.credit_static','silver.previous_applications','gold.abt','gold.monthly_metrics'}
        or not isinstance(manifest['validations'],dict) or not manifest['validations'] or any(not isinstance(v,dict) or v.get('status')!='passed' for v in manifest['validations'].values())):
        raise ValueError('Publicação não aprovada ou coorte incompatível')
    for table in manifest['tables'].values():
        if (not isinstance(table,dict) or not isinstance(table.get('uri'),str) or not table['uri'].startswith('s3a://')
            or not isinstance(table.get('delta_table_id'),str) or not table['delta_table_id']
            or type(table.get('version')) is not int or table['version']<0
            or type(table.get('rows')) is not int or table['rows']<0):
            raise ValueError('Metadados de tabela inválidos')
    timestamp(snapshot['observed_at_utc'])
    if snapshot['verification_level'] not in ('manifest_and_pointer','delta_tables'):raise ValueError('Verificação desconhecida')
    return manifest


def observe(repo, sample, client=None, *, offline=False, verify_tables=False, spark_factory=None):
    cache=repo/'artifacts/f09/status'/sample/'last_observed_publication.json'
    error=None
    if not offline:
        spark=None
        try:
            from src.object_store.publication import current, open_object_publication
            from src.object_store.spark import create_object_spark
            registry=client.config['prefix']+'/operational-publications/'+sample
            pointer,_=current(client,registry)
            raw=client.get(registry+'/manifests/'+pointer['publication_id']+'.json')[0].decode()
            snapshot={'format_version':1,'pointer':pointer,'manifest_json':raw,
                'observed_at_utc':datetime.now(timezone.utc).isoformat(),'verification_level':'manifest_and_pointer'}
            validate_snapshot(snapshot,sample)
            if verify_tables:
                spark=(spark_factory or create_object_spark)(repo,app_name='lakehouse-status-reader')
                with open_object_publication(client,registry,spark,pointer['publication_id']):pass
                spark.stop();spark=None
                snapshot['verification_level']='delta_tables'
            snapshot['pointer_changed_during_read']=current(client,registry)[0]!=pointer
            atomic_json(cache,snapshot)
            return {**snapshot,'availability':'online','is_current_observation':not snapshot['pointer_changed_during_read']}
        except Exception as caught:
            error={'error_type':type(caught).__name__,'error':str(caught)}
        finally:
            if spark is not None:
                try:spark.stop()
                except Exception as cleanup:
                    detail={'error_type':type(cleanup).__name__,'error':str(cleanup)}
                    if error is None:error=detail
                    else:error['cleanup_error']=detail
    if cache.is_file():
        try:
            snapshot=json.loads(cache.read_text());validate_snapshot(snapshot,sample)
            return {**snapshot,'availability':'cached','is_current_observation':False,'observation_error':error}
        except (ValueError,TypeError,KeyError,OSError) as caught:
            error={'error_type':type(caught).__name__,'error':str(caught)}
    return {'availability':'unavailable','is_current_observation':False,'observation_error':error}


def compose(sample, operations, diagnostics, observation, policy, *, now=None):
    now=now or datetime.now(timezone.utc);alerts=[]
    def warn(code,message,severity='warning'):alerts.append({'code':code,'severity':severity,'message':message})
    latest=operations[0] if operations else None
    successful=next((o for o in operations if o['status']=='passed'),None)
    failures=[o for o in operations if o['status'] in ('failed','cancelled')]
    unfinished=[o for o in operations if o['status'] in ('running','retry_wait')]
    if policy.get('status')!='validated':warn('alert_policy_unavailable','Calibração indisponível; limites de desempenho não foram aplicados.')
    if not operations:warn('no_operation_history','Nenhuma operação local encontrada.')
    if diagnostics:warn('incomplete_history','Há relatórios ilegíveis/inválidos; a última execução é a última conhecida.')
    if latest and latest['status'] in ('failed','cancelled'):warn('latest_operation_failed','A última operação conhecida não terminou com sucesso.')
    if unfinished:warn('unfinished_reports','Há relatórios sem estado final; isso não comprova processos ativos.')
    if observation['availability']!='online':warn('publication_not_currently_observed','CURRENT não foi confirmado nesta consulta; cache é apenas uma observação anterior.')
    if observation.get('pointer_changed_during_read'):warn('pointer_changed','CURRENT mudou durante a leitura; repetir a consulta para atualizar a observação.')
    profile=None
    if successful:
        match={k:successful['options'].get(k) for k in ('sample','mode','batch')}
        profile=next((p for p in policy['profiles'] if p['match']==match),None)
        if profile:
            duration=successful.get('timing',{}).get('total_seconds');rss=successful.get('resources',{}).get('peak_process_tree_rss_bytes')
            if duration is not None and duration>profile['duration_warning_seconds']:warn('duration_above_local_baseline',f"A última operação bem-sucedida excedeu {policy['duration_factor']:g}× a duração de referência local.")
            if rss is not None and rss>profile['rss_warning_bytes']:warn('rss_above_local_baseline',f"A última operação bem-sucedida excedeu {policy['rss_factor']:g}× o RSS de referência local.")
        else:warn('no_comparable_baseline','Sem baseline calibrada para este modo/lote/coorte; nenhum limite de desempenho foi inventado.','info')
    publication=None
    if observation['availability']!='unavailable':
        manifest=validate_snapshot(observation,sample)
        publication={'publication_id':manifest['publication_id'],'observed_at_utc':observation['observed_at_utc'],
            'availability':observation['availability'],'is_current_observation':observation['is_current_observation'],
            'verification_level':observation['verification_level'],'manifest_sha256':observation['pointer']['manifest_sha256'],
            'tables':{name:{k:t[k] for k in ('uri','delta_table_id','version','rows')} for name,t in manifest['tables'].items()},
            'quality':{'status':'passed','source':'approved_manifest_not_recomputed_quality','validations':manifest['validations']}}
    def brief(record):
        if record is None:return None
        return {key:record.get(key) for key in ('operation_id','status','stage','started_at_utc','finished_at_utc','exit_code','options','report','report_sha256','timing','resources','attempts','result')}
    return {'format_version':1,'selection_id':sample,'observed_at_utc':now.isoformat(),
        'health':'attention' if any(a['severity']=='warning' for a in alerts) else 'ok',
        'latest_execution':brief(latest),'last_successful_execution':brief(successful),
        'failure_count_total':len(failures),'failures':[brief(o) for o in failures[:10]],'unfinished':[brief(o) for o in unfinished],
        'history_complete':not diagnostics,'history_diagnostics':diagnostics,'publication':publication,
        'publication_observation_error':observation.get('observation_error'),'alerts':alerts,
        'alert_policy':policy,'matched_baseline':profile,
        'scope':'point-in-time local summary; quality is the stored publication approval; cached publication is never claimed as current'}


def markdown(report):
    latest=report['latest_execution'];pub=report['publication']
    lines=['# Resumo operacional', '',f"Seleção: `{report['selection_id']}` · Estado: **{report['health']}**",'',
        f"Última execução conhecida: `{latest['operation_id']}` — {latest['status']} ({latest['stage']})." if latest else 'Nenhuma execução local encontrada.',
        f"Publicação observada: `{pub['publication_id']}` — {pub['availability']}; CURRENT confirmado agora: {pub['is_current_observation']}." if pub else 'Publicação indisponível; CURRENT não confirmado.', '']
    if pub:
        lines += [f"Qualidade registrada: {pub['quality']['status']}; verificação: {pub['verification_level']}; observação: {pub['observed_at_utc']}.", '',
            '| Tabela | Versão | Linhas |','|---|---:|---:|']
        lines += [f"| {name} | {t['version']} | {t['rows']} |" for name,t in pub['tables'].items()]
        lines += ['']
    if latest:
        lines += [f"Relatório da execução: `{latest['report']}`.",'']
        if latest['attempts']:
            a=latest['attempts'][-1]
            if a.get('error'):lines += [f"Falha: {a.get('category',a.get('error_type'))}: {a['error']}",'']
    successful=report['last_successful_execution']
    if successful:
        lines += [f"Última operação bem-sucedida: `{successful['operation_id']}`.",'']
        if successful.get('timing'):
            lines += [f"Duração medida: {successful['timing']['total_seconds']:.3f} s.",'']
    if report['matched_baseline']:
        p=report['matched_baseline']
        lines += [f"Alertas locais acima de {p['duration_warning_seconds']:.3f} s ou {p['rss_warning_bytes']} bytes RSS para o modo/lote/coorte comparável.",'']
    if report['failures']:
        lines += ['Falhas/cancelamentos recentes (até 10):','','| Operação | Estado | Etapa | Saída |','|---|---|---|---:|']
        lines += [f"| {o['operation_id']} | {o['status']} | {o['stage']} | {o['exit_code']} |" for o in report['failures']]
        lines += ['']
    lines += ['Alertas:','']+[f"- {a['code']}: {a['message']}" for a in report['alerts']]
    if not report['alerts']:lines += ['- Nenhum alerta local.']
    lines += ['',f"Falhas/cancelamentos listados: {len(report['failures'])}; relatórios sem estado final: {len(report['unfinished'])}.",
        'Limites são referências locais, não SLA. Cache e aprovação armazenada não substituem uma nova verificação das tabelas.','']
    return '\n'.join(lines)
