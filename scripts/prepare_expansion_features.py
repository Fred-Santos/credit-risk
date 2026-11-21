"""Materializa o contrato de atributos fixos a partir da seleção revisada."""
import csv
from pathlib import Path
import yaml
from src.expansion.silver import load_contract
from src.expansion.features import load_features,feature_catalog
from src.pipelines.download_home_credit import sha256


def main():
    root=Path(__file__).resolve().parents[1]
    silver=root/'configs/contracts/expansion_silver_v1.yaml'
    policy=root/'configs/expansion_features_v1.yaml'
    definitions=root/'data/raw/feature_definitions.csv'
    contract=load_contract(silver);config=load_features(policy,contract)
    lookup={r['Variable']:r['Description'] for r in csv.DictReader(definitions.open())}
    result=feature_catalog(config,contract,lookup)
    result.update(silver_contract_sha256=sha256(silver),feature_policy_sha256=sha256(policy),dictionary_sha256=sha256(definitions))
    (root/'configs/contracts/expansion_gold_v1.yaml').write_text(yaml.safe_dump(result,sort_keys=False,allow_unicode=True))
    selected={(f['source_table'],f['source_column']) for f in result['features'] if f['source_column']}
    source_catalog={}
    for table,spec in contract['tables'].items():
        source_catalog[table]={}
        for column,dtype in spec['input_schema'].items():
            if column=='target':role,reason='label_only','never_predictor'
            elif column in ('case_id','num_group1','num_group2','personindex_1023L'):role,reason='identifier_or_local_index','not_person_identity_or_predictor'
            elif column in ('date_decision','MONTH','WEEK_NUM'):role,reason='population_metadata','temporal_split_and_audit_only'
            elif column.startswith('_'):role,reason='lineage_only','technical_metadata_not_predictor'
            elif (table,column) in selected:role,reason='selected_retrospective','availability_unproven'
            else:role,reason='silver_only','not_selected_in_v1_no_target_driven_selection'
            if column.startswith('riskassesment_'):role,reason='silver_only','external_score_training_vintage_and_availability_unknown'
            source_catalog[table][column]={'raw_type':dtype,'silver_type':spec['schema'][column],'role':role,'reason':reason}
    (root/'configs/contracts/expansion_feature_sources_v1.yaml').write_text(yaml.safe_dump({'version':1,'tables':source_catalog},sort_keys=False))
    print('Catálogo:',len(result['features']),'atributos retrospectivos; elegíveis PIT:',len(result['eligible_predictors']))


if __name__=='__main__':main()
