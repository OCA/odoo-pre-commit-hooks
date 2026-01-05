import unittest

import pytest
from fixit.config import collect_rules
from fixit.ftypes import Config
from fixit.testing import generate_lint_rule_test_cases

from oca_pre_commit_hooks import utils


class FixitTest(unittest.TestCase):
    def test_fixit(self):
        """Run 'fixit test' based on fixit.cli.test method"""
        mp = pytest.MonkeyPatch()
        mp.setenv("FIXIT_ODOO_VERSION", "18.0")
        mp.setenv("FIXIT_AUTOFIX", "True")
        rule = utils.fixit_parse_rule()
        lint_rules = collect_rules(Config(enable=[rule], disable=[], python_version=None))
        assert lint_rules, "Not found rules"
        test_cases = generate_lint_rule_test_cases(lint_rules)
        assert test_cases, "Not found test cases"
        print("")
        for test_case_class in test_cases:
            with self.subTest(rule_class=test_case_class.__name__):
                suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_case_class)
                for test in suite:
                    test_result = unittest.TestResult()
                    test.run(test_result)
                    if test_result.failures or test_result.errors:
                        print(f"❌ Failed: {test.id()}")
                        for _fail, traceback in test_result.failures + test_result.errors:
                            print(traceback)
                        self.fail(f"Subtest {test.id()} failed")
                    else:
                        print(f"✅ Subtest {test.id()} passed")
