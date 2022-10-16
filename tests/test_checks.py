import glob
import unittest

import oca_pre_commit_hooks

ALL_CODE_ERRORS = {
    "missing_readme",
    "po_duplicate_message_definition",
    "po_python_parse_format",
    "po_python_parse_printf",
    "po_requires_module",
    "xml_create_user_wo_reset_password",
    "xml_dangerous_filter_wo_user",
    "xml_dangerous_qweb_replace_low_priority",
    "xml_deprecated_openerp_xml_node",
    "xml_deprecated_qweb_directive",
    "xml_deprecated_tree_attribute",
    "xml_duplicate_fields",
    "xml_duplicate_record_id",
    "xml_not_valid_char_link",
    "xml_redundant_module_name",
    "xml_syntax_error",
    "xml_view_dangerous_replace_low_priority",
}


class TestChecks(unittest.TestCase):
    # TODO: Test manifest, po, xml and csv syntax error
    # TODO: csv without ID
    # TODO: Force xml_deprecated_data_node
    # TODO: Force csv_duplicate_record_id

    @staticmethod
    def get_all_code_errors(all_check_errors):
        check_errors_keys = set()
        for check_errors in all_check_errors:
            check_errors_keys |= set(check_errors.keys())
        return check_errors_keys

    def test_checks(self):
        manifest_paths = glob.glob("./test_repo/*/__openerp__.py") + glob.glob("./test_repo/*/__manifest__.py")
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(manifest_paths, do_exit=False, verbose=True)
        all_code_errors = self.get_all_code_errors(all_check_errors)
        self.assertEqual(ALL_CODE_ERRORS, all_code_errors)

    def test_non_exists_path(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run("/tmp/no_exists", do_exit=False, verbose=True)
        check_errors_keys = self.get_all_code_errors(all_check_errors)
        self.assertEqual({"manifest_syntax_error"}, check_errors_keys)
