"""Controle nativo de um serviço loopback; parar nunca remove dados."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import time

from src.bronze.build_bronze import _ingestion_lock
from src.object_store.config import load_config,local_path,credentials
from src.publication.protocol import atomic_json


def _running(pid):
    try:
        status=Path(f'/proc/{pid}/stat').read_text().split()[2]
        return status!='Z'
    except FileNotFoundError:
        return False


class ObjectService:
    def __init__(self,repo):
        self.repo=Path(repo).resolve()
        self.config=load_config(self.repo)
        self.control=local_path(self.repo,self.config['control_directory'])
        self.control.mkdir(parents=True,exist_ok=True)
        self.pid_file=self.control/'service.json'
        self.binary=self.repo/'.runtime/object-store/bin/weed'
        self.data=local_path(self.repo,self.config['data_directory'])

    def _pid(self):
        if not self.pid_file.exists():return None
        record=json.loads(self.pid_file.read_text())
        if record['data_directory']!=str(self.data) or record['binary']!=str(self.binary):
            raise ValueError('Registro do serviço não pertence a esta instalação')
        pid=record['pid']
        if not _running(pid):return None
        command=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        if str(self.binary).encode() not in command or ('-dir='+str(self.data)).encode() not in command:
            raise RuntimeError('PID foi reutilizado por outro processo; não sinalizar')
        return pid

    def _secrets(self):
        path=local_path(self.repo,self.config['secret_file'])
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            value={'access_key':secrets.token_hex(16),'secret_key':secrets.token_hex(32)}
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as handle:json.dump(value,handle)
        value=credentials(self.repo,self.config)
        auth=self.control/'s3-auth.json'
        content={'identities':[{'name':'local-lakehouse','credentials':[
            {'accessKey':value['access_key'],'secretKey':value['secret_key']}],
            'actions':['Admin','Read','Write','List','Tagging']}]}
        descriptor=os.open(auth,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(descriptor,'w') as handle:json.dump(content,handle)
        return auth

    def start(self,timeout=45):
        with _ingestion_lock(self.control,'.service.lock'):
            pid=self._pid()
            if pid:return {'status':'running','pid':pid,'reused':True,'endpoint':self.config['endpoint']}
            if not self.binary.is_file():raise FileNotFoundError('Execute bash scripts/bootstrap_objects.sh')
            auth=self._secrets()
            self.data.mkdir(parents=True,exist_ok=True)
            config=self.config
            # Reservas de validação são fechadas antes de lançar o servidor.
            for port in [config[n] for n in ('master_port','volume_port','filer_port','s3_port','admin_port')]:
                for candidate in (port,port+10000):
                    with socket.socket() as check:
                        check.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                        check.bind(('127.0.0.1',candidate))
            command=[str(self.binary),'mini','-dir='+str(self.data),'-ip=127.0.0.1','-ip.bind=127.0.0.1',
                '-master.port='+str(config['master_port']),'-volume.port='+str(config['volume_port']),
                '-filer.port='+str(config['filer_port']),'-s3.port='+str(config['s3_port']),
                '-s3.config='+str(auth),'-master.volumeSizeLimitMB=128','-volume.max=32',
                '-webdav=false','-admin.ui=false','-admin.port.legacy=0',
                '-admin.port='+str(config['admin_port']),'-admin.port.grpc='+str(config['admin_port']+10000),
                '-s3.port.iceberg=0','-s3.port.lance=0','-master.telemetry=false',
                '-master.vacuumIntervalSeconds=0','-volume.preStopSeconds=1']
            environment=dict(os.environ)
            # O parser Go também lê flags do ambiente; o host usa debug=release.
            environment.update(debug='false',DEBUG='false')
            with (self.control/'server.log').open('ab') as log:
                process=subprocess.Popen(command,stdout=log,stderr=log,stdin=subprocess.DEVNULL,
                    cwd=self.data,start_new_session=True,env=environment)
            atomic_json(self.pid_file,{'pid':process.pid,'binary':str(self.binary),'data_directory':str(self.data)})
            deadline=time.monotonic()+timeout
            from src.object_store.client import ObjectClient
            client=ObjectClient(self.repo)
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise RuntimeError('SeaweedFS encerrou na inicialização; consulte server.log')
                try:
                    client.ensure_bucket()
                    return {'status':'running','pid':process.pid,'reused':False,'endpoint':config['endpoint']}
                except Exception:
                    time.sleep(.25)
            os.kill(process.pid,signal.SIGTERM)
            raise TimeoutError('SeaweedFS não ficou pronto dentro do limite')

    def stop(self,timeout=30):
        with _ingestion_lock(self.control,'.service.lock'):
            pid=self._pid()
            if pid is None:return {'status':'stopped','reused':True,'data_preserved':True}
            os.kill(pid,signal.SIGTERM)
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline and _running(pid):time.sleep(.1)
            if _running(pid):raise TimeoutError('Serviço não encerrou; dados preservados, sem SIGKILL automático')
            return {'status':'stopped','reused':False,'data_preserved':True}

    def status(self):
        pid=self._pid()
        return {'status':'running' if pid else 'stopped','pid':pid,'endpoint':self.config['endpoint'],
                'data_directory':self.data.relative_to(self.repo).as_posix()}

    def listeners(self):
        pid=self._pid()
        if pid is None:return []
        inodes=set()
        for path in Path(f'/proc/{pid}/fd').iterdir():
            try:target=os.readlink(path)
            except FileNotFoundError:continue
            if target.startswith('socket:['):inodes.add(target[8:-1])
        result=[]
        for line in Path(f'/proc/{pid}/net/tcp').read_text().splitlines()[1:]:
            fields=line.split()
            if fields[3]!='0A' or fields[9] not in inodes:continue
            address,port=fields[1].split(':')
            host=socket.inet_ntoa(bytes.fromhex(address)[::-1])
            result.append({'host':host,'port':int(port,16)})
        return sorted(result,key=lambda item:item['port'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','stop','restart','status'])
    args=parser.parse_args()
    service=ObjectService(Path(__file__).resolve().parents[2])
    if args.action=='restart':service.stop();result=service.start()
    else:result=getattr(service,args.action)()
    print(json.dumps(result))


if __name__=='__main__':main()
