from pathlib import Path
from urllib.parse import urlsplit
import json

import yaml


def load_config(repo: Path):
    config=yaml.safe_load((repo/'configs/object_store_v1.yaml').read_text())
    fixed={'version':1,'provider':'seaweedfs','provider_version':'4.53',
        'release_url':'https://github.com/seaweedfs/seaweedfs/releases/download/4.53/linux_amd64.tar.gz',
        'release_sha256':'d1a7dec9f48d8b33895a0ea8951971defc2dc5312906dcc76fa5a5f74a6ee90d',
        'region':'us-east-1','bucket':'credit-risk-local','prefix':'lakehouse-v1','bind':'127.0.0.1',
        'control_directory':'.runtime/object-store/control','data_directory':'data/object-store/seaweedfs',
        'secret_file':'.runtime/object-store/credentials.json','hadoop_aws':'3.3.4',
        'aws_java_sdk_bundle':'1.12.262','delta_log_store':'io.delta.storage.S3SingleDriverLogStore',
        'writer':'one_cooperating_host_and_one_spark_driver','retention_days':30,'real_vacuum':'forbidden'}
    if any(config.get(k)!=v for k,v in fixed.items()):
        raise ValueError('Política do armazenamento de objetos não suportada')
    ports=[config[n] for n in ('master_port','volume_port','filer_port','s3_port','admin_port')]
    if any(type(p) is not int or not 1024<=p<55000 for p in ports) or len(set(ports+[p+10000 for p in ports]))!=10:
        raise ValueError('Portas locais inválidas ou sobrepostas')
    if config['endpoint']!=f"http://127.0.0.1:{config['s3_port']}":
        raise ValueError('Endpoint precisa ser loopback e corresponder à porta S3')
    if set(config)!=set(fixed)|{'endpoint','master_port','volume_port','filer_port','s3_port','admin_port'}:
        raise ValueError('Configuração contém campos inesperados')
    if type(config['version']) is not int or type(config['retention_days']) is not int:
        raise ValueError('Versão e retenção precisam ser inteiros')
    return config


def local_path(repo: Path,value: str):
    path=(repo/value).resolve()
    if not path.is_relative_to(repo.resolve()) or path==repo.resolve() or Path(value).is_absolute():
        raise ValueError('Caminho de controle fora do repositório')
    return path


def credentials(repo,config):
    path=local_path(repo,config['secret_file'])
    if path.stat().st_mode & 0o077:
        raise ValueError('Credenciais locais precisam de permissão 0600')
    value=json.loads(path.read_text())
    if set(value)!={'access_key','secret_key'} or any(not isinstance(v,str) or len(v)<20 for v in value.values()):
        raise ValueError('Credenciais locais inválidas')
    return value


def s3_key(value):
    if (not isinstance(value,str) or not value or value.startswith('/') or '\\' in value
            or any(p in ('','..','.') for p in value.rstrip('/').split('/'))):
        raise ValueError('Chave S3 relativa inválida')
    return value
