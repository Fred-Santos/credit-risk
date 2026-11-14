import unittest
from src.operation.lineage import column_lineage, validate_links, MODEL_SHA
from src.gold.model import ABT_SCHEMA,MONTH_SCHEMA


class OperationalLineageTests(unittest.TestCase):
    def fixture(self):
        op={'status':'passed','options':{'sample':'cohort','mode':'replay','batch':'first'},
            'result':{'run_id':'reader','publication_id':'publication'},'attempts':[{'run_id':'reader','status':'passed'}]}
        run={'status':'passed','run_id':'reader','publication_id':'publication','selection_id':'cohort',
             'mode':'replay','batch':'first','source_versions':{'cases':1},'fingerprints':{'producer':'hash'}}
        manifest={'publication_id':'publication','identity':{'scope':'operational_analytics_v1','selection_id':'cohort',
            'source_versions':{'cases':1},'state_identity':{'fingerprints':{'producer':'hash'}}},
            'provenance':{'src/gold/model.py':{'sha256':MODEL_SHA}}}
        return op,run,manifest

    def test_all_columns_have_reviewed_lineage_and_constant_has_no_fake_source(self):
        rules=column_lineage(MODEL_SHA)
        self.assertEqual(set(rules['gold.abt']),set(ABT_SCHEMA))
        self.assertEqual(set(rules['gold.monthly_metrics']),set(MONTH_SCHEMA))
        self.assertEqual(rules['gold.abt']['_abt_contract_version']['sources'],[])
        self.assertIn('silver.previous_applications.credamount_590A',rules['gold.abt']['previous_amount_sum']['sources'])
        self.assertEqual(rules['gold.abt']['previous_amount_sum']['transform'],'ordered_double_sum_null_when_no_non_null')

    def test_unknown_model_never_gets_lineage_of_current_code(self):
        with self.assertRaises(ValueError):column_lineage('0'*64)

    def test_reused_publication_does_not_require_creation_run_equal_to_reader(self):
        op,run,manifest=self.fixture()
        self.assertEqual(validate_links(op,run,manifest)['model_sha256'],MODEL_SHA)

    def test_wrong_attempt_population_limit_or_publication_is_rejected(self):
        for group,key,value in [('result','run_id','other'),('options','sample','other'),('options','batch','other'),('result','publication_id','other')]:
            op,run,manifest=self.fixture();op[group][key]=value
            with self.assertRaises(ValueError):validate_links(op,run,manifest)
        op,run,manifest=self.fixture();op['attempts'][0]['status']='failed'
        with self.assertRaises(ValueError):validate_links(op,run,manifest)

    def test_versions_and_producer_bindings_are_not_inferred_from_latest_state(self):
        for key,value in [('source_versions',{'cases':2}),('state_identity',{'fingerprints':{'producer':'changed'}})]:
            op,run,manifest=self.fixture();manifest['identity'][key]=value
            with self.assertRaises(ValueError):validate_links(op,run,manifest)
        op,run,manifest=self.fixture();run['status']='failed'
        with self.assertRaises(ValueError):validate_links(op,run,manifest)
