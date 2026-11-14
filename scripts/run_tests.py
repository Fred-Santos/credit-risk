"""Runner por responsabilidade; integrações obrigatórias nunca aceitam skips."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
GROUPS=('unit','spark','delta','objects','analysis','e2e')


def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item


def selected_tests(root, group):
    manifest=json.loads((root/'tests/suites.json').read_text())
    tests=list(flatten(unittest.TestLoader().discover(str(root/'tests'))))
    classes={t.id().rsplit('.',1)[0] for t in tests}
    if classes!=set(manifest['classes']):
        raise ValueError('Catálogo divergente: '+str({'unclassified':sorted(classes-set(manifest['classes'])),
            'not_discovered':sorted(set(manifest['classes'])-classes)}))
    if manifest['version']!=1 or set(manifest['classes'].values())-set(GROUPS):raise ValueError('Catálogo inválido')
    ids=[t.id() for t in tests]
    if len(set(ids))!=len(ids):raise ValueError('IDs de teste duplicados')
    chosen=[t for t in tests if group=='all' or manifest['classes'][t.id().rsplit('.',1)[0]]==group]
    if not chosen:raise ValueError('Suíte vazia')
    return chosen,manifest


class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.records=[];self.started={};self.outcomes={}
    def startTest(self,test):
        self.started[test.id()]=time.perf_counter();super().startTest(test)
    def addSuccess(self,test):self.outcomes[test.id()]='passed';super().addSuccess(test)
    def addFailure(self,test,error):self.outcomes[test.id()]='failed';super().addFailure(test,error)
    def addError(self,test,error):self.outcomes[test.id()]='error';super().addError(test,error)
    def addSkip(self,test,reason):self.outcomes[test.id()]='skipped';super().addSkip(test,reason)
    def addExpectedFailure(self,test,error):self.outcomes[test.id()]='expected_failure';super().addExpectedFailure(test,error)
    def addUnexpectedSuccess(self,test):self.outcomes[test.id()]='unexpected_success';super().addUnexpectedSuccess(test)
    def addSubTest(self,test,subtest,error):
        if error is not None:self.outcomes[test.id()]='failed'
        super().addSubTest(test,subtest,error)
    def stopTest(self,test):
        self.records.append({'id':test.id(),'status':self.outcomes.get(test.id(),'error'),
            'duration_seconds':time.perf_counter()-self.started[test.id()]});super().stopTest(test)


def accepted(result, required):
    return result.wasSuccessful() and (not required or not result.skipped) and not result.expectedFailures


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration-required',action='store_true')
    parser.add_argument('--suite',choices=('all',*GROUPS),default='all')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--report',type=Path,default=ROOT/'artifacts/tests/report.json')
    args=parser.parse_args();tests,manifest=selected_tests(ROOT,args.suite)
    counts=Counter(manifest['classes'][t.id().rsplit('.',1)[0]] for t in tests)
    if args.list:
        print(json.dumps({'suite':args.suite,'count':len(tests),'groups':counts,'ids':[t.id() for t in tests]},indent=2));return 0
    started=time.perf_counter()
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordedResult).run(unittest.TestSuite(tests))
    passed=accepted(result,args.integration_required)
    report={'status':'passed' if passed else 'failed','suite':args.suite,'tests':result.testsRun,
        'duration_seconds':time.perf_counter()-started,'skipped':len(result.skipped),'groups':counts,
        'catalogue_sha256':hashlib.sha256((ROOT/'tests/suites.json').read_bytes()).hexdigest(),
        'integration_required':args.integration_required,'results':result.records,
        'errors':[{'id':t.id(),'traceback':trace} for t,trace in result.errors+result.failures],
        'counting':'subprocess wrappers count once here; inner scenarios are reported by their suites'}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    if args.integration_required and result.skipped:print('Integração obrigatória: testes ignorados impedem aprovação.',file=sys.stderr)
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
