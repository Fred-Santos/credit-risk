"""Cópia imutável de entradas aprovadas para objetos, conferida por SHA-256."""
import json
from pathlib import Path

from src.pipelines.download_home_credit import sha256
from src.quality.contracts import load_contract,source_fingerprints
from src.quality.event_contracts import digest
from src.silver.read_bronze import verify_approval


def mirror_inputs(ctx,client,bound,f04_report_path):
    repo=ctx.repo_root
    gate=verify_approval(bound)
    report=json.loads(f04_report_path.read_text())
    if report['status']!='passed' or report['selection_id']!=bound.ctx.selection_id:
        raise ValueError('Mirror exige a execução F04 aprovada da seleção')
    raw=source_fingerprints(ctx.raw_dir,load_contract(repo/'configs/contracts/home_credit_v1.yaml'))
    identity={'selection_id':bound.ctx.selection_id,'raw':raw,'bronze_gate_sha256':gate['gate_sha256'],
              'f04_report_sha256':sha256(f04_report_path)}
    mirror_id=digest(identity)[:24]
    prefix=client.config['prefix']+'/inputs/'+mirror_id
    paths={}
    for name in raw:paths[(ctx.raw_dir/name).relative_to(repo).as_posix()]=ctx.raw_dir/name
    for directory in (bound.ctx.ingestion_dir,bound.ctx.bronze_dir,repo/report['events_root']):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not path.name.startswith('.') and not path.name.endswith('.lock'):
                if not path.resolve().is_relative_to(directory.resolve()):raise ValueError('Entrada fora do namespace')
                paths[path.relative_to(repo).as_posix()]=path
    paths[f04_report_path.relative_to(repo).as_posix()]=f04_report_path
    for name,expected in report['identity']['binding']['artifacts'].items():
        path=repo/name
        if sha256(path)!=expected:raise ValueError('Implementação histórica F04 não corresponde aos arquivos atuais')
        paths[name]=path
    ready=json.loads((bound.ctx.bronze_dir/'_READY.json').read_text())
    run_path=repo/ready['run_report'];paths[run_path.relative_to(repo).as_posix()]=run_path
    run=json.loads(run_path.read_text())
    for section in ('quality','reconciliation','lineage'):
        path=repo/run[section]['json']
        if not path.is_file():path=bound.ctx.docs_root/run[section]['json']
        paths[path.relative_to(repo).as_posix()]=path
    files={}
    for name,path in sorted(paths.items()):
        checksum=sha256(path);key=prefix+'/'+name
        if client.exists(key):
            if client.checksum(key)!=checksum:raise ValueError('Mirror S3 existente diverge da origem')
        else:
            client.put_new(key,path.read_bytes())
        if sha256(path)!=checksum or client.checksum(key)!=checksum:raise RuntimeError('Cópia S3 perdeu integridade')
        files[name]={'key':key,'sha256':checksum,'bytes':path.stat().st_size}
    manifest={'format_version':1,'status':'passed','mirror_id':mirror_id,'identity':identity,'files':files}
    client.put_json(prefix+'/_INPUTS.json',manifest)
    return manifest,prefix+'/_INPUTS.json'


def verify_mirror(client,manifest):
    if manifest.get('status')!='passed' or digest(manifest['identity'])[:24]!=manifest['mirror_id']:
        raise ValueError('Mirror S3 não aprovado')
    for record in manifest['files'].values():
        if client.checksum(record['key'])!=record['sha256']:raise ValueError('Entrada espelhada mudou')


def mirrored_directory(client,manifest,relative):
    prefix=client.config['prefix']+'/inputs/'+manifest['mirror_id']+'/'+relative.rstrip('/')
    if not any(record['key'].startswith(prefix+'/') for record in manifest['files'].values()):
        raise ValueError('Dataset não consta do mirror aprovado')
    return client.uri(prefix)
