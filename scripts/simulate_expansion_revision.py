"""Uma correção auxiliar real em namespace privado, declarada como simulação."""
import json
from pathlib import Path
from pyspark.sql import functions as F
from src.expansion.silver import open_silver
from src.expansion.revisions import apply_revision
from src.expansion.storage import verify_package
from src.pipelines.download_home_credit import sha256
from src.publication.protocol import atomic_json


def simulate(repo,spark,parent,contract):
    manifest,frames=open_silver(repo,spark,parent)
    root=repo/'artifacts/expansion/revision_demo'/manifest['id'];root.mkdir(parents=True,exist_ok=True)
    event_manifest=root/'event.json'
    if not event_manifest.exists():
        frame=frames['train_other_1'].orderBy('case_id','num_group1').limit(1)
        corrected=frame.withColumn('amtdebitincoming_4809443A',F.col('amtdebitincoming_4809443A')+F.lit(1.0))\
            .withColumn('_source_revision',F.lit(2).cast('long')).withColumn('_is_simulated',F.lit(True))
        target=root/'events';corrected.write.parquet(str(target))
        atomic_json(event_manifest,{'is_simulated':True,'description':'Declared auxiliary correction: +1 source-transformed unit, revision 2',
            'tables':{'train_other_1':{'path':str(target.relative_to(repo)),
                'files':{p.name:sha256(p) for p in target.glob('*.parquet')}}}})
    before=sha256(parent/'_silver.json')
    child,reused=apply_revision(repo,spark,parent,contract,event_manifest)
    again,second_reused=apply_revision(repo,spark,parent,contract,event_manifest)
    if not second_reused or again['id']!=child['id'] or child['affected_cases']['rows']!=1:
        raise ValueError('Replay ou rastreio de dependências inválido')
    if sha256(parent/'_silver.json')!=before:raise ValueError('Pai modificado')
    verify_package(parent,'_silver.json')
    atomic_json(root/'result.json',{'status':'passed','baseline_id':manifest['id'],'child_id':child['id'],
        'affected_cases':child['affected_cases'],'parent_preserved':True,'second_reused':second_reused,
        'changed_sources':child['changed_sources'],'is_simulated':True})
    return child,reused
