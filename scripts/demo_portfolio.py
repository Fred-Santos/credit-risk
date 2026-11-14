"""Demonstração S3/Delta com dados inventados e saída revisável; não lê Home Credit."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from publication_fixture import fixture_frames
from src.gold.model import load_gold_contract
from src.gold.publish import prepare_gold
from src.object_store.client import ObjectClient
from src.object_store.fixtures import temporary_objects
from src.object_store.publication import current,publish_object_snapshot,verify_publication,registry_key
from src.object_store.service import ObjectService
from src.object_store.spark import create_object_spark
from src.publication.evolution import prepare_silver
from src.publication.protocol import InjectedFailure,fail_at
from src.utils.run_context import RunContext


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(output):
    output=output.resolve()
    if output.exists():raise FileExistsError('Escolha um diretório de saída novo')
    output.mkdir(parents=True)
    started=time.perf_counter();service=ObjectService(ROOT);owned=service.status()['status']!='running';spark=None
    report={'status':'running','data_kind':'invented_synthetic_fixture','input_stage':'typed_silver_fixture',
            'scope':'one host; S3/Delta publication demonstration; RAW path tested separately in F10',
            'steps':[],'fingerprints':{p:digest(ROOT/p) for p in ['scripts/demo_portfolio.py','tests/publication_fixture.py','src/gold/model.py','src/gold/publish.py','src/object_store/publication.py']}}
    def export(frames,label):
        values={}
        for name in ['gold.abt','gold.monthly_metrics']:
            order='case_id' if name=='gold.abt' else 'MONTH'
            frame=frames[name];rows=[r.asDict() for r in frame.orderBy(order).collect()]
            target=output/(label+'_'+name.replace('.','_')+'.csv')
            with target.open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=frame.columns);writer.writeheader();writer.writerows(rows)
            values[name]=rows
        return values
    try:
        service.start();spark=create_object_spark(ROOT,app_name='portfolio-synthetic-demo')
        spec=load_gold_contract(ROOT/'configs/contracts/gold_v1.yaml',ROOT/'configs/contracts/silver_managed_v2.yaml')
        with temporary_objects(ROOT) as client:
            prefix=client.config['prefix'];registry=registry_key(client,'a'*24)
            def publish(label,corrected=False,parent=None,hook=None):
                data,plan=fixture_frames(spark,corrected=corrected);counts={n:f.count() for n,f in data.items()}
                def builder(tx):
                    silver=prepare_silver(tx,data,plan,counts)
                    prepare_gold(tx,silver,spec,parent=parent)
                return publish_object_snapshot(RunContext.create(ROOT),client,registry,spark,
                    {'scope':'portfolio_synthetic_demo','selection_id':'a'*24,'snapshot':label,'fixture':prefix},
                    report['fingerprints'],builder,hook=hook)[0]
            baseline=publish('baseline')
            _,frames=verify_publication(client,registry,baseline['publication_id'],spark)
            before=export(frames,'baseline')
            assert len(before['gold.abt'])==3 and before['gold.abt'][0]['previous_amount_sum']==5
            assert before['gold.monthly_metrics'][0]['target_1_rate']==.5
            report['steps'].append({'step':'load_and_query','status':'passed','publication_id':baseline['publication_id'],'cases':3,'months':2})
            parent={'manifest':baseline,'frames':frames,'silver':{n:frames['silver.'+n] for n in ('credit_cases','credit_static','previous_applications')}}
            try:publish('corrected',True,parent,fail_at('after_commit:gold.abt:merge'))
            except InjectedFailure:pass
            else:raise AssertionError('A falha prevista não ocorreu')
            assert current(client,registry)[0]['publication_id']==baseline['publication_id']
            report['steps'].append({'step':'failure_after_private_gold_merge','status':'passed','current_preserved':True})
            corrected=publish('corrected',True,parent)
            _,updated=verify_publication(client,registry,corrected['publication_id'],spark)
            after=export(updated,'corrected');case=after['gold.abt'][0]
            assert case['static_annuity']==11 and case['previous_amount_sum']==6
            assert len(after['gold.abt'])==3
            commits=corrected['details']['gold_update']['commits_this_attempt']
            assert commits=={'inserts':0,'updates':0},commits
            assert after['gold.monthly_metrics']==before['gold.monthly_metrics']
            report['steps'].append({'step':'resume_and_correct','status':'passed','publication_id':corrected['publication_id'],'extra_merge_rows_on_retry':commits,'case_1':{'static_annuity_before':10,'static_annuity_after':case['static_annuity'],'history_sum_before':5,'history_sum_after':case['previous_amount_sum']}})
            _,old=verify_publication(client,registry,baseline['publication_id'],spark)
            historical=export(old,'historical');assert historical==before
            assert current(client,registry)[0]['publication_id']==corrected['publication_id']
            report['steps'].append({'step':'historical_read','status':'passed','same_values_as_baseline':True,'current_still_corrected':True})
        assert not ObjectClient(ROOT).list(prefix+'/')
        report['temporary_prefix_removed']=True
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        if spark is not None:spark.stop()
        if owned:service.stop()
        report['duration_seconds']=time.perf_counter()-started
        report['outputs']={p.name:digest(p) for p in sorted(output.glob('*.csv'))}
        (output/'report.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
    print(json.dumps({'status':report['status'],'report':str(output/'report.json'),'duration_seconds':report['duration_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    execute(parser.parse_args().output)
