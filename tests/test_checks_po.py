import glob
import os

import oca_pre_commit_hooks
from . import common

RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"
RE_CHECK_OUTPUT = r"\- \[(?P<check>[\w|-]+)\]"

ALL_CHECK_CLASS = [
    oca_pre_commit_hooks.checks_odoo_module_po.ChecksOdooModulePO,
]

EXPECTED_ERRORS = {
    "po-duplicate-message-definition": 3,
    "po-python-parse-format": 4,
    "po-python-parse-printf": 2,
    "po-requires-module": 1,
    "po-syntax-error": 2,
}


class TestChecksPO(common.ChecksCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        test_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo")
        po_glob_pattern = os.path.join(test_repo_path, "**", "*.po")
        pot_glob_pattern = f"{po_glob_pattern}t"
        cls.file_paths = glob.glob(po_glob_pattern, recursive=True) + glob.glob(pot_glob_pattern, recursive=True)

    def setUp(self):
        super().setUp()
        self.expected_errors = EXPECTED_ERRORS.copy()
        self.checks_run = oca_pre_commit_hooks.checks_odoo_module_po.run
        self.checks_cli_main = oca_pre_commit_hooks.cli.main_po

    def test_non_exists_path(self):
        all_check_errors = self.checks_run(["/tmp/no_exists"], no_exit=True, no_verbose=False)
        real_errors = self.get_count_code_errors(all_check_errors)
        self.assertDictEqual(real_errors, {"po-syntax-error": 1})
