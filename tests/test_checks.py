import glob
import os
import sys
import unittest
from collections import defaultdict

import oca_pre_commit_hooks

EXPECTED_ERRORS = {
    "csv_duplicate_record_id": 1,
    "manifest_syntax_error": 2,
    "missing_readme": 1,
    "po_duplicate_message_definition": 3,
    "po_python_parse_format": 4,
    "po_python_parse_printf": 2,
    "po_requires_module": 1,
    "xml_create_user_wo_reset_password": 1,
    "xml_dangerous_filter_wo_user": 1,
    "xml_dangerous_qweb_replace_low_priority": 3,
    "xml_deprecated_data_node": 8,
    "xml_deprecated_openerp_xml_node": 5,
    "xml_deprecated_qweb_directive": 2,
    "xml_deprecated_tree_attribute": 3,
    "xml_duplicate_fields": 9,
    "xml_duplicate_record_id": 3,
    "xml_not_valid_char_link": 2,
    "xml_redundant_module_name": 1,
    "xml_syntax_error": 2,
    "xml_view_dangerous_replace_low_priority": 6,
}


class TestChecks(unittest.TestCase):
    # TODO: Test manifest, po, xml and csv syntax error
    # TODO: Test manifest without init file
    # TODO: Test folder without manifest
    # TODO: Test CSV without ID
    # TODO: Test modules without CSV or XML or PO

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifest_paths = glob.glob("./test_repo/*/__openerp__.py") + glob.glob("./test_repo/*/__manifest__.py")
        cls.module_paths = [os.path.dirname(i) for i in cls.manifest_paths]
        cls.maxDiff = None

    def setUp(self):
        super().setUp()
        self.expected_errors = EXPECTED_ERRORS.copy()

    @staticmethod
    def get_all_code_errors(all_check_errors):
        check_errors_keys = set()
        for check_errors in all_check_errors:
            check_errors_keys |= set(check_errors.keys())
        return check_errors_keys

    @staticmethod
    def get_count_code_errors(all_check_errors):
        check_errors_count = defaultdict(int)
        for check_errors in all_check_errors:
            for check, errors in check_errors.items():
                check_errors_count[check] += len(errors)
        return check_errors_count

    def test_checks(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
            self.manifest_paths, do_exit=False, verbose=True
        )
        real_errors = self.get_count_code_errors(all_check_errors)
        # Uncommet to get sorted values to update EXPECTED_ERRORS dict
        # print('\n'.join(f"'{key}':{count_code_errors[key]}," for key in sorted(count_code_errors)))
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_checks_with_sys_argv_module_paths_verbose(self):
        sys.argv = [""] + self.module_paths
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(do_exit=False, verbose=False)
        real_errors = self.get_count_code_errors(all_check_errors)
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_non_exists_path(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(["/tmp/no_exists"], do_exit=False, verbose=True)
        check_errors_keys = self.get_all_code_errors(all_check_errors)
        self.assertEqual({"manifest_syntax_error"}, check_errors_keys)
