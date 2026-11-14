"""Conferência local de pacote: arquivos permitidos, outputs e segredos conhecidos."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def known_secrets():
    tokens=[]
    for path in (ROOT/'.runtime/object-store/credentials.json',ROOT/'.kaggle/kaggle.json',ROOT/'kaggle.json'):
        if path.is_file():
            try:tokens += [v.encode() for v in json.loads(path.read_text()).values() if isinstance(v,str) and len(v)>=16]
            except (ValueError,AttributeError):pass
    path=ROOT/'.kaggle/access_token'
    if path.is_file() and len(path.read_bytes().strip())>=16:tokens.append(path.read_bytes().strip())
    return tokens


def audit(bundle):
    bundle=Path(bundle).resolve();manifest=json.loads((bundle/'source_manifest.json').read_text())
    expected=set(manifest['sources'])|{'source_manifest.json'}
    actual={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    # Auditar o export novo, antes de bootstrap/testes acrescentarem artefatos.
    if actual!=expected:raise ValueError('Pacote contém arquivos não catalogados')
    errors=[];tokens=known_secrets()
    for name,record in manifest['sources'].items():
        path=bundle/name;raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=record['export_sha256']:errors.append(name+':hash')
        if path.suffix.lower() in ('.parquet','.csv','.zip','.log','.tar','.db'):errors.append(name+':data_extension')
        if any(part in ('.kaggle','.aws','.git','.venv','.runtime','data','artifacts') for part in Path(name).parts):errors.append(name+':private_path')
        if any(token in raw for token in tokens):errors.append(name+':credential_match')
        if path.suffix=='.ipynb':
            d=json.loads(raw)
            if any(c.get('outputs') or c.get('execution_count') is not None or c.get('attachments') for c in d['cells']):errors.append(name+':notebook_output')
    original=[]
    for path in (ROOT/'notebooks').glob('*.ipynb'):
        d=json.loads(path.read_text());original.append({'path':path.relative_to(ROOT).as_posix(),
            'cells_with_outputs':sum(bool(c.get('outputs')) for c in d['cells']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    tracked=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=False).stdout.decode().split('\0')
    tracked=[p for p in tracked if p]
    sensitive_tracked=[n for n in tracked if Path(n).suffix.lower() in ('.parquet','.csv','.zip') or any(p in ('.aws','.kaggle','.runtime','.venv') for p in Path(n).parts)]
    secret_paths=[n for n in tracked if (ROOT/n).is_file() and any(t in (ROOT/n).read_bytes() for t in tokens)]
    result={'status':'passed' if not errors and not secret_paths else 'failed','bundle_files':len(actual),'errors':errors,
        'known_secret_values_checked':len(tokens),'tracked_credential_matches':secret_paths,'tracked_data_like_paths_for_review':sensitive_tracked,
        'historical_notebooks':original,'original_working_tree_publication_ready':False,
        'scope':'sanitized code package only; historical notebook preserved as hash-bound input; external publication and data rights remain F11 review'}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);p.add_argument('--report',required=True);a=p.parse_args()
    result=audit(a.bundle);target=Path(a.report);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));raise SystemExit(0 if result['status']=='passed' else 1)
