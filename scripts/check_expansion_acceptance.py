"""Gate E08: matriz da expansão ligada ao catálogo e à execução obrigatória."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from run_tests import ROOT,selected_tests


def check(report=None):
    matrix=json.loads((ROOT/'tests/expansion_acceptance_matrix.json').read_text())
    if matrix['version']!=1 or [r['id'] for r in matrix['scenarios']]!=[f'X{i:02}' for i in range(1,18)]:
        raise ValueError('Matriz da expansão inválida')
    tests,_=selected_tests(ROOT,'all');ids={t.id() for t in tests};executed=None
    if report:
        report=Path(report);value=json.loads(report.read_text())
        if value['status']!='passed' or not value['integration_required'] or value['skipped']:
            raise ValueError('Execução obrigatória não aprovada')
        executed={r['id']:r['status'] for r in value['results']}
        if set(executed)!=ids or value['tests']!=len(ids) or any(v!='passed' for v in executed.values()):
            raise ValueError('Relatório não corresponde ao catálogo completo aprovado')
        e2e=ROOT/'artifacts/expansion/e08/expansion_e2e.json'
        result=json.loads(e2e.read_text())
        if result['status']!='passed' or not result['raw_to_expansion_s3'] or result['kaggle_access']:
            raise ValueError('E2E da expansão não demonstrado')
    output=[]
    for row in matrix['scenarios']:
        if not row['tests'] or not set(row['tests'])<=ids:raise ValueError('Teste desconhecido: '+row['id'])
        for entry in row['nested']:
            tree=ast.parse((ROOT/entry['file']).read_text())
            if entry['method'] not in {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}:
                raise ValueError('Cenário interno ausente')
        output.append({'id':row['id'],'status':'passed' if executed else 'mapped','tests':row['tests']})
    return {'status':'passed','scope':'full executed suite and expansion e2e' if executed else 'static mapping only',
        'matrix_sha256':hashlib.sha256((ROOT/'tests/expansion_acceptance_matrix.json').read_bytes()).hexdigest(),'scenarios':output}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    result=check(a.report)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'scope':result['scope'],'scenarios':len(result['scenarios'])}))
