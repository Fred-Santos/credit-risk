"""Cópia de código para CI: sem dados, credenciais, outputs de notebook ou runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def export(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Destino deve ser novo')
    if destination==ROOT or ROOT.is_relative_to(destination):raise ValueError('Destino não pode conter a origem')
    destination.mkdir(parents=True)
    files=[]
    for directory in ('src','scripts','tests','configs','notebooks','.github'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.sh','.yaml','.yml','.json','.xml','.ipynb') and '__pycache__' not in p.parts:
                if p.name=='operational_matrix_local.py':continue
                if p.is_symlink():raise ValueError('Symlink de fonte não permitido')
                files.append(p)
    files += [p for p in ROOT.iterdir() if p.is_file() and (p.name.startswith('requirements') or p.name in ('LICENSE','.gitignore'))]
    files=sorted(set(files),key=lambda p:p.relative_to(ROOT).as_posix())
    for p in files:
        target=destination/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        if target.suffix=='.ipynb':
            notebook=json.loads(target.read_text());notebook['metadata']={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}}
            for cell in notebook['cells']:
                cell['metadata']={};cell.pop('attachments',None)
                if cell['cell_type']=='code':cell['outputs']=[];cell['execution_count']=None
            target.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n')
    def pin(relative,field,reference):
        p=destination/relative;text=p.read_text(encoding='utf-8-sig')
        updated,count=re.subn(r'^'+re.escape(field)+r': [0-9a-f]{64}$',field+': '+sha(destination/reference),text,flags=re.M)
        if count!=1:raise ValueError('Referência de hash não encontrada: '+relative+':'+field)
        p.write_text(updated)
    pin('configs/silver_policy_v1.yaml','notebook_sha256','notebooks/analise_silver.ipynb')
    pin('configs/contracts/silver_initial_v1.yaml','silver_policy_sha256','configs/silver_policy_v1.yaml')
    pin('configs/contracts/silver_managed_v2.yaml','parent_contract_sha256','configs/contracts/silver_initial_v1.yaml')
    pin('configs/contracts/gold_v1.yaml','silver_contract_sha256','configs/contracts/silver_managed_v2.yaml')
    manifest={'format_version':1,'scope':'sanitized_code_for_fixture_validation_not_final_portfolio',
        'excluded':['data','artifacts','.runtime','.venv','.git','.kaggle','.aws','.env','docs','local_real_data_matrix'],
        'notebook_outputs_removed':True,'sources':{p.relative_to(ROOT).as_posix():{'original_sha256':sha(p),'export_sha256':sha(destination/p.relative_to(ROOT))} for p in files}}
    (destination/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'status':'passed','destination':str(destination),'files':len(files)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    print(json.dumps(export(parser.parse_args().output)))
