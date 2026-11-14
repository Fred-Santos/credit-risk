"""Gráficos derivados exclusivamente dos CSVs sintéticos produzidos pela demo."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(output):
    report=json.loads((output/'report.json').read_text());assert report['status']=='passed'
    assert report['data_kind']=='invented_synthetic_fixture'
    for name,sha in report['outputs'].items():assert hashlib.sha256((output/name).read_bytes()).hexdigest()==sha
    def case(label):
        with (output/(label+'_gold_abt.csv')).open() as handle:return next(csv.DictReader(handle))
    baseline,corrected=case('baseline'),case('corrected')
    plt.rcParams['svg.hashsalt']='credit-risk-synthetic-demo-v1'
    fig,axes=plt.subplots(1,2,figsize=(8,3.5))
    for ax,column,title in zip(axes,['static_annuity','previous_amount_sum'],['Anuidade: caso inventado 1','Soma histórica: caso inventado 1']):
        ax.bar(['Inicial','Corrigido'],[float(baseline[column]),float(corrected[column])],color=['#386cb0','#1b9e77'])
        ax.set_title(title,fontsize=10);ax.set_ylabel('Unidade da fixture')
    fig.suptitle('Dados sintéticos — correção das auxiliares; população permanece em 3 casos')
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(output/('correction.'+ext),metadata={'Date':None} if ext=='svg' else {})
    plt.close(fig)
    (output/'figures.json').write_text(json.dumps({'status':'passed','data_kind':'invented_synthetic_fixture','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('correction.*'))}},indent=2)+'\n')
    print('Gráficos sintéticos gravados em '+str(output))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);render(parser.parse_args().output)
