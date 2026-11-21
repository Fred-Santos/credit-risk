"""Pacotes locais imutáveis; ativação CURRENT permanece na fase E07."""
import hashlib
import json
from pathlib import Path
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json
from src.silver.initial_delta import _files


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def safe_path(repo,relative):
    path=(repo/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(repo.resolve()):
        raise ValueError('Caminho fora do repositório')
    return path


def pin_delta(spark,path,relative,rows):
    from delta.tables import DeltaTable
    delta=DeltaTable.forPath(spark,str(path))
    return {'path':relative,'version':int(delta.history(1).select('version').first()[0]),
            'delta_table_id':delta.detail().select('id').first()[0],
            'schema':dict(spark.read.format('delta').load(str(path)).dtypes),'rows':rows}


def open_pin(repo,spark,entry):
    from delta.tables import DeltaTable
    path=safe_path(repo,entry['path'])
    table=DeltaTable.forPath(spark,str(path))
    if table.detail().select('id').first()[0]!=entry['delta_table_id']:
        raise ValueError('UUID Delta divergente')
    frame=spark.read.format('delta').option('versionAsOf',entry['version']).load(str(path))
    if dict(frame.dtypes)!=entry['schema']:
        raise ValueError('Schema Delta divergente')
    return frame


def verify_package(root,filename,identity=None):
    manifest=json.loads((root/filename).read_text())
    if (manifest['status']!='passed' or manifest['id']!=root.name
            or digest(manifest['identity'])!=manifest['identity_sha256']
            or manifest['id']!=manifest['identity_sha256'][:24]
            or (identity is not None and manifest['identity']!=identity)
            or manifest['files']!=_files(root)):
        raise ValueError('Pacote ausente, alterado ou identidade inválida')
    return manifest


def finish_package(stage,destination,manifest,filename):
    manifest.update(status='passed',files=_files(stage))
    atomic_json(stage/filename,manifest)
    # Destinos dos pins já apontam para o caminho final; nenhuma leitura privada é exposta.
    stage.rename(destination)
    return manifest


def code_fingerprints(paths):
    return {str(p):sha256(Path(p)) for p in paths}
