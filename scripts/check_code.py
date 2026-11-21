"""Verificações adotadas: sintaxe Python/shell, YAML e cobertura do catálogo."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_tests import selected_tests


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--report",type=Path,default=ROOT/"artifacts/tests/code_checks.json");args=parser.parse_args()
    python_files=[p for folder in ('src','scripts','tests') for p in (ROOT/folder).rglob('*.py')]
    for p in python_files:compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
    shells=list((ROOT/'scripts').glob('*.sh'))
    for p in shells:subprocess.run(['bash','-n',str(p)],check=True)
    configs=list((ROOT/'configs').rglob('*.yaml'))+list((ROOT/'.github').rglob('*.yml'))
    for p in configs:
        if not isinstance(yaml.safe_load(p.read_text(encoding='utf-8-sig')),dict):raise ValueError('YAML sem mapping: '+str(p))
    tests,manifest=selected_tests(ROOT,'all')
    from check_acceptance import check
    check()
    from check_expansion_acceptance import check as check_expansion
    check_expansion()
    result={'status':'passed','python_files':len(python_files),'shell_files':len(shells),'yaml_files':len(configs),
            'catalogued_tests':len(tests),'check_scope':'syntax and catalogue; not a style reformat or type checker'}
    target=args.report;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
