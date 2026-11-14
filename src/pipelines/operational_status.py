"""Resumo pontual da operação; consulta não inicia o serviço S3."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from src.operation.status import alert_profiles, load_history, observe, compose, markdown
from src.object_store.client import ObjectClient
from src.object_store.publication import identifier
from src.publication.protocol import atomic_json
from src.pipelines.download_home_credit import sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--offline',action='store_true',help='Não acessar S3; cache não comprova CURRENT')
    group.add_argument('--verify-tables',action='store_true',help='Verificar arquivos, UUIDs, versões e linhas com Spark')
    parser.add_argument('--json',action='store_true',help='Imprimir o resumo estruturado completo')
    args=parser.parse_args()
    try:identifier(args.sample)
    except ValueError as error:parser.error(str(error))
    repo=Path(__file__).resolve().parents[2]
    try:policy=alert_profiles(repo)
    except Exception as error:policy={'status':'unavailable','profiles':[],'error_type':type(error).__name__,'error':str(error)}
    operations,diagnostics=load_history(repo,args.sample)
    client=None;connection_error=None
    if not args.offline:
        try:client=ObjectClient(repo)
        except Exception as error:connection_error={'error_type':type(error).__name__,'error':str(error)}
    observation=observe(repo,args.sample,client,offline=args.offline or connection_error is not None,verify_tables=args.verify_tables)
    if connection_error:observation['observation_error']=connection_error
    report=compose(args.sample,operations,diagnostics,observation,policy)
    status_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    report['status_run_id']=status_id
    report['implementation']={name:sha256(repo/name) for name in ('src/operation/status.py','src/pipelines/operational_status.py')}
    report['policy_file_sha256']=sha256(repo/'configs/operational_alerts_v1.yaml') if (repo/'configs/operational_alerts_v1.yaml').is_file() else None
    output=repo/'artifacts/f09/status'/args.sample/(status_id+'.json')
    atomic_json(output,report);output.with_suffix('.md').write_text(markdown(report))
    if args.json:print(json.dumps({**report,'summary_report':str(output)}))
    else:print(markdown(report)+'\nResumo completo: '+str(output))
    return 1 if args.verify_tables and (observation['availability']!='online' or observation['verification_level']!='delta_tables') else 0


if __name__=='__main__':raise SystemExit(main())
