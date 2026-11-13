from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import yaml

from src.analytics.queries import load_analysis_policy
from src.pipelines.download_home_credit import sha256
from src.pipelines.run_analysis import require_triplet

ROOT=Path(__file__).resolve().parents[1]


class AnalysisPolicyTests(unittest.TestCase):
    def test_policy_cannot_relax_population_or_nulls_silently(self):
        policy=load_analysis_policy(ROOT/'configs/analysis_policy_v1.yaml')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'policy.yaml'
            for change in ({'version':True},{'small_group_min_cases':500.0},
                           {'population':'drop_missing_values'},{'valid_labels':[1]},
                           {'label_maturity':'audited'},{'source_mutation':'allowed'}):
                path.write_text(yaml.safe_dump({**policy,**change}))
                with self.subTest(change=change),self.assertRaises(ValueError):
                    load_analysis_policy(path)

    def test_publications_must_have_matching_selection_contract_and_parent_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp)
            registry=repo/'registry'
            (registry/'manifests').mkdir(parents=True)
            ids={'baseline':'a'*24,'corrected':'b'*24,'final':'c'*24}
            for value in ids.values():
                (registry/'manifests'/(value+'.json')).write_text(value)
            docs={label:{'publication_id':value,'identity':{'scope':'analytics_v1','selection_id':'s',
                'gold_contract_sha256':'contract','parent_analytics':None}} for label,value in ids.items()}
            for child,parent in (('corrected','baseline'),('final','corrected')):
                path=registry/'manifests'/(ids[parent]+'.json')
                docs[child]['identity']['parent_analytics']={'manifest':path.relative_to(repo).as_posix(),'sha256':sha256(path)}
            require_triplet(repo,registry,docs,'s')
            for field,value in (('selection_id','other'),('scope','silver_v2'),
                                ('gold_contract_sha256','other'),('parent_analytics',None)):
                changed=deepcopy(docs)
                changed['corrected']['identity'][field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):
                    require_triplet(repo,registry,changed,'s')
