import os
import unittest
from pathlib import Path

from fixit.config import collect_rules, parse_rule
from fixit.ftypes import Config
from fixit.testing import generate_lint_rule_test_cases

from oca_pre_commit_hooks import checks_odoo_module_fixit


class FixitTest(unittest.TestCase):
    def test_fixit(self):
        """Run 'fixit test' based on fixit.cli.test method"""
        os.environ["FIXIT_ODOO_VERSION"] = "18.0"
        os.environ["FIXIT_AUTOFIX"] = "True"

        rule = parse_rule(
            ".checks_odoo_module_fixit",
            Path(os.path.dirname(os.path.dirname(os.path.abspath(checks_odoo_module_fixit.__file__)))),
        )
        lint_rules = collect_rules(Config(enable=[rule], disable=[], python_version=None))
        test_cases = generate_lint_rule_test_cases(lint_rules)
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
