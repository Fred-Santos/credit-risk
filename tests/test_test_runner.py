import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('project_test_runner',Path(__file__).resolve().parents[1]/'scripts/run_tests.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class TestRunnerContractTests(unittest.TestCase):
    def test_required_integration_rejects_skip(self):
        class Sample(unittest.TestCase):
            @unittest.skip('missing dependency fixture')
            def test_missing(self):pass
        result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(Sample).run(result)
        self.assertFalse(runner.accepted(result,True));self.assertTrue(runner.accepted(result,False))

    def test_failure_and_expected_failure_are_not_acceptance(self):
        class Sample(unittest.TestCase):
            @unittest.expectedFailure
            def test_known_problem(self):self.fail('fixture')
        result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(Sample).run(result)
        self.assertFalse(runner.accepted(result,True))

    def test_empty_group_and_uncatalogued_test_are_errors(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'tests').mkdir();(root/'tests/suites.json').write_text(json.dumps({'version':1,'classes':{}}))
            with self.assertRaises(ValueError):runner.selected_tests(root,'unit')
            (root/'tests/test_unmapped_fixture.py').write_text('import unittest\nclass Unmapped(unittest.TestCase):\n    def test_example(self):pass\n')
            with self.assertRaises(ValueError):runner.selected_tests(root,'unit')
