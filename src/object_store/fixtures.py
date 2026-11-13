"""Fixtures geradas internamente; nenhuma rotina recebe um destino para apagar."""
from contextlib import contextmanager
from pathlib import Path
import socket
import tempfile
import uuid

import yaml

from src.object_store.client import ObjectClient
from src.object_store.service import ObjectService


@contextmanager
def temporary_objects(repo):
    client=ObjectClient(repo)
    prefix='fixtures/f08/'+uuid.uuid4().hex
    bucket=client.bucket
    client.config={**client.config,'prefix':prefix}
    try:yield client
    finally:
        # O prefixo fechado é criado aqui; não usar config mutável do caller.
        for key in client.list(prefix+'/'):
            client.s3.delete_object(Bucket=bucket,Key=key)


def capability_probe(repo):
    from botocore.exceptions import ClientError
    with temporary_objects(repo) as client:
        key=client.config['prefix']+'/preconditions.json'
        first=client.put_new(key,b'initial')
        try:client.put_new(key,b'other')
        except ValueError:pass
        else:raise AssertionError('If-None-Match não protege objeto imutável')
        try:client.replace(key,b'bad','"wrong-etag"')
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode']!=412:raise
        else:raise AssertionError('If-Match incorreto foi aceito')
        if client.get(key)[0]!=b'initial':raise AssertionError('Precondição falha alterou o objeto')
        client.replace(key,b'updated',first)
        if client.get(key)[0]!=b'updated' or key not in client.list(client.config['prefix']+'/'):
            raise AssertionError('GET/listagem não observam o PUT concluído')
        try:ObjectClient(repo,wrong_credentials=True).s3.head_bucket(Bucket=client.bucket)
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode'] not in (403,404):raise
        else:raise AssertionError('Credenciais incorretas aceitas')
        prefix=client.config['prefix']
    if ObjectClient(repo).list(prefix+'/'):raise AssertionError('Fixture de objetos não foi removida')
    return {'status':'passed','authentication_enforced':True,'failed_conditions_preserve_content':True,
        'conditional_put_and_consistent_list_observed':True,'fixture_objects_removed':True,
        'scope':'serial_local_probe_not_distributed_concurrency_proof'}


def lifecycle_fixture(repo):
    """Serviço próprio em TemporaryDirectory, com portas livres e dados sintéticos."""
    config=yaml.safe_load((repo/'configs/object_store_v1.yaml').read_text())
    with tempfile.TemporaryDirectory(prefix='credit_risk_objects_') as directory:
        root=Path(directory)
        (root/'configs').mkdir()
        candidates=None
        for offset in range(50):
            primary=[31000+offset*50+i*7 for i in range(5)]
            reservations=[]
            try:
                for port in primary+[p+10000 for p in primary]:
                    check=socket.socket();check.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                    reservations.append(check);check.bind(('127.0.0.1',port))
                candidates=primary;break
            except OSError:pass
            finally:
                for check in reservations:check.close()
        if candidates is None:raise RuntimeError('Sem portas para fixture de serviço')
        for name,port in zip(('master_port','volume_port','filer_port','s3_port','admin_port'),candidates):config[name]=port
        config['endpoint']=f"http://127.0.0.1:{config['s3_port']}"
        (root/'configs/object_store_v1.yaml').write_text(yaml.safe_dump(config))
        binary=root/'.runtime/object-store/bin/weed';binary.parent.mkdir(parents=True)
        binary.symlink_to(repo/'.runtime/object-store/bin/weed')
        service=ObjectService(root)
        try:
            service.start();client=ObjectClient(root)
            key='fixture/persistent.json';client.put_json(key,{'amount':10})
            checksum=client.checksum(key)
            before=service.listeners()
            if not before or any(r['host']!='127.0.0.1' for r in before):raise AssertionError('Fixture expôs porta externa')
            service.stop()
            if not service.data.is_dir():raise AssertionError('Parar removeu os dados')
            service.start()
            if client.checksum(key)!=checksum:raise AssertionError('Reinício perdeu persistência')
            service.stop()
            result={'status':'passed','stopping_preserves_directory':True,'restart_preserves_object':True,
                'all_listeners_loopback':True,'fixture_root':str(root)}
        finally:service.stop()
    if root.exists():raise AssertionError('Diretório temporário não foi removido')
    return {**result,'internally_created_lab_removed':True,'real_data_removed':False}
