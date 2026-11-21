"""Cenário E07: duas publicações, falhas, retry, leitura histórica e rollback."""
from pathlib import Path
import uuid
from src.expansion.publication import publish,consume,registry
from src.expansion.quality import compare_keyed
from src.expansion.storage import verify_package,safe_path
from src.object_store.publication import current,activate_object_publication
from src.publication.protocol import atomic_json
from src.utils.run_context import RunContext


class DeliveryFault(RuntimeError):pass


def exercise(repo,client,spark,baseline,corrected,output):
    base,base_report=publish(repo,client,spark,*baseline)
    reg=registry(client,base['identity']['selection_id']);baseline_id=base['publication_id']
    record={'status':'running','baseline_id':baseline_id,'registry':reg,'faults':[],
            'baseline_attempt':base_report,'current_restored_to_real_baseline':False}
    def fail(point):
        def hook(stage):
            if stage==point:raise DeliveryFault(point)
        return hook
    corrected_id=None
    try:
        for point in ('after_copy:silver.train_base','before_pointer','after_pointer'):
            injected=True
            try:
                _,attempt=publish(repo,client,spark,*corrected,hook=fail(point),allow_simulated=True)
            except DeliveryFault:pass
            else:
                if point!='after_copy:silver.train_base' or not attempt['reused']:
                    raise AssertionError('Falha injetada não foi atingida')
                # Reexecutar a matriz não recria nem apaga uma publicação já aprovada.
                injected=False
                activate_object_publication(RunContext.create(repo),client,reg,spark,baseline_id)
            now=current(client,reg)[0]['publication_id']
            expected=baseline_id if point!='after_pointer' else now
            if point!='after_pointer' and now!=expected:raise AssertionError('Falha privada alterou CURRENT')
            if point=='after_pointer' and now==baseline_id:raise AssertionError('Falha após ativação não ativou a nova publicação')
            record['faults'].append({'stage':point,'current_after_failure':now,'status':'passed' if injected else 'verified_reuse_no_new_copy','injected':injected})
        changed,retry=publish(repo,client,spark,*corrected,allow_simulated=True)
        corrected_id=changed['publication_id'];record.update(corrected_id=corrected_id,retry=retry)
        if not retry['reused'] or current(client,reg)[0]['publication_id']!=corrected_id:raise AssertionError('Retry não recuperou publicação ativada')
        old,old_frames=consume(client,spark,base['identity']['selection_id'],baseline_id,include_evaluation_labels=True)
        new,new_frames=consume(client,spark,base['identity']['selection_id'],corrected_id,include_evaluation_labels=True)
        record['correction_proofs']={}
        changed_total=0
        for period in ('development','evaluation'):
            key='gold.'+period+'_features'
            proof=compare_keyed(old_frames[key],new_frames[key],['case_id'],numeric_tolerance=(1e-8,1e-10))
            if proof['missing_rows'] or proof['extra_rows']:raise AssertionError('Correção mudou a população')
            changed_total+=proof['changed_rows'];record['correction_proofs'][key]=proof
            labels='gold.'+period+'_labels'
            proof=compare_keyed(old_frames[labels],new_frames[labels],['case_id'])
            if not proof['success']:raise AssertionError('Correção auxiliar mudou rótulos')
            record['correction_proofs'][labels]=proof
        if changed_total!=1:raise AssertionError('Correção não se restringiu a um caso Gold')
        _,default_frames=consume(client,spark,base['identity']['selection_id'],baseline_id)
        if 'gold.evaluation_labels' in default_frames:raise AssertionError('Leitor padrão expôs rótulos de avaliação')
        record['default_reader_hides_evaluation_labels']=True
        record['historical_reads_passed']=True
        record['status']='passed'
    finally:
        # Mesmo uma falha de verificação posterior à ativação não deixa a simulação como CURRENT.
        activation=activate_object_publication(RunContext.create(repo),client,reg,spark,baseline_id)
        record['rollback']=activation
        record['current_restored_to_real_baseline']=current(client,reg)[0]['publication_id']==baseline_id
        atomic_json(output,record)
    return record
