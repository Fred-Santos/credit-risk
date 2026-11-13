"""Binário nativo fixado por SHA; não extrai caminhos arbitrários do tar."""
from io import BytesIO
from pathlib import Path
import hashlib
import os
import subprocess
import tarfile

import requests
import yaml


def main():
    root=Path(__file__).resolve().parents[1]
    config=yaml.safe_load((root/'configs/object_store_v1.yaml').read_text())
    directory=root/'.runtime/object-store/bin'
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/'weed'
    archive=directory/'linux_amd64.tar.gz'
    expected=config['release_sha256']
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        response=requests.get(config['release_url'],timeout=120)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest()!=expected:
            raise ValueError('Checksum da release SeaweedFS inválido')
        temporary=archive.with_suffix('.download')
        temporary.write_bytes(response.content)
        os.replace(temporary,archive)
    with tarfile.open(fileobj=BytesIO(archive.read_bytes()),mode='r:gz') as bundle:
        candidates=[m for m in bundle.getmembers() if Path(m.name).name=='weed' and m.isfile()]
        if len(candidates)!=1:
            raise ValueError('Release deve conter exatamente um binário weed regular')
        data=bundle.extractfile(candidates[0]).read()
    if not target.is_file() or target.read_bytes()!=data:
        temporary=target.with_suffix('.new')
        temporary.write_bytes(data)
        temporary.chmod(0o755)
        os.replace(temporary,target)
    result=subprocess.run([str(target),'version'],check=True,capture_output=True,text=True)
    if config['provider_version'] not in result.stdout.split():
        raise ValueError('Versão do binário não corresponde à configuração')
    print(result.stdout.strip())


if __name__=='__main__':main()
