"""Vincula os 24 cenários ao catálogo e, opcionalmente, ao resultado executado."""
import argparse
import ast
import json
from pathlib import Path
from run_tests import ROOT, selected_tests


def check(report=None):
    matrix=json.loads((ROOT/'tests/acceptance_matrix.json').read_text())
    assert matrix['version']==1
    assert [r['id'] for r in matrix['scenarios']]==[f'T{i:02}' for i in range(1,25)],'Matriz incompleta ou repetida'
    tests,_=selected_tests(ROOT,'all');ids={t.id() for t in tests}
    results=None
    if report:
        value=json.loads(Path(report).read_text())
        assert value['status']=='passed' and value['integration_required'] and value['skipped']==0
        results={r['id']:r['status'] for r in value['results']}
        assert set(results)==ids and value['tests']==len(ids),'Relatório não corresponde ao catálogo atual'
    output=[]
    for row in matrix['scenarios']:
        assert row['tests'] and set(row['tests'])<=ids,row['id']+': teste desconhecido'
        for nested in row['nested']:
            path=ROOT/nested['file'];tree=ast.parse(path.read_text())
            assert nested['method'] in {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)},nested
        if results:assert all(results[t]=='passed' for t in row['tests']),row['id']+': não aprovado'
        output.append({'id':row['id'],'status':'passed' if results else 'mapped','tests':row['tests'],'nested':row['nested']})
    return {'status':'passed','scope':'executed full suite' if results else 'static mapping only','scenarios':output}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=check(args.report)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'scope':result['scope'],'scenarios':len(result['scenarios'])}))
