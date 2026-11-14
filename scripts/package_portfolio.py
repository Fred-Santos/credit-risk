"""Empacota somente código sanitizado, documentação selecionada e demo sintética."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import export_source
import audit_source

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def package(demo,output,report_path):
    demo=demo.resolve();output=output.resolve()
    if output.exists():raise FileExistsError('Destino deve ser novo')
    run=json.loads((demo/'report.json').read_text());figures=json.loads((demo/'figures.json').read_text())
    assert run['status']=='passed' and run['data_kind']=='invented_synthetic_fixture'
    assert len(run['steps'])==4 and all(s['status']=='passed' for s in run['steps'])
    assert run['temporary_prefix_removed'] and figures['status']=='passed'
    with tempfile.TemporaryDirectory(prefix='credit-risk-portfolio-') as folder:
        source=Path(folder)/'source';export_source.export(source)
        review=audit_source.audit(source);assert review['status']=='passed',review
        readme=(ROOT/'docs/entrega/PACOTE_SINTETICO.md').read_text()
        for name in ['DEMONSTRACAO','ARQUITETURA','REPRODUCAO']:
            readme=readme.replace(']('+name+'.md)','](docs/entrega/'+name+'.md)')
        (source/'README.md').write_text(readme)
        for name in ['ARQUITETURA','DEMONSTRACAO','REPRODUCAO','PACOTE_SINTETICO']:
            target=source/'docs/entrega'/(name+'.md');target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/'docs/entrega'/(name+'.md'),target)
        image=source/'docs/entrega/imagens/correcao_sintetica.png';image.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(demo/'correction.png',image)
        dest=source/'demo';dest.mkdir()
        for name,expected in {**run['outputs'],**figures['files']}.items():
            assert Path(name).name==name and sha(demo/name)==expected
            shutil.copyfile(demo/name,dest/name)
        for name in ['report.json','figures.json']:shutil.copyfile(demo/name,dest/name)
        tokens=audit_source.known_secrets()
        entries={}
        for p in sorted(source.rglob('*')):
            if p.is_file():
                assert not p.is_symlink() and not any(t in p.read_bytes() for t in tokens)
                entries[p.relative_to(source).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
        manifest={'version':1,'scope':'sanitized_code_and_invented_demo_only','external_publication_performed':False,
            'restricted_data_included':False,'notebook_outputs':0,'files':entries}
        (source/'portfolio_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        output.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(output,'w:gz') as tar:
            for p in sorted(source.rglob('*')):
                if p.is_file():tar.add(p,arcname=p.relative_to(source).as_posix(),recursive=False)
        with tarfile.open(output) as tar:
            assert len(tar.getmembers())==len(entries)+1
            for m in tar.getmembers():
                assert m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts
                if m.name!='portfolio_manifest.json':assert hashlib.sha256(tar.extractfile(m).read()).hexdigest()==entries[m.name]['sha256']
    result={'status':'passed','package':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'files':len(entries)+1,
        'known_secret_values_checked':len(tokens),'source_audit_status':review['status'],'scope':manifest['scope'],
        'external_publication_performed':False,'restricted_data_included':False}
    report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();package(args.demo,args.output,args.report)
