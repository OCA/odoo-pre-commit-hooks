import glob
import unittest

import oca_pre_commit_hooks

ALL_CHECKS = {
    "xml_not_valid_char_link",
    "xml_deprecated_qweb_directive",
    "xml_create_user_wo_reset_password",
    "xml_deprecated_openerp_xml_node",
}


class TestChecks(unittest.TestCase):
    def test_checks(self):
        manifest_paths = glob.glob("./test_repo/*/__openerp__.py") + glob.glob("./test_repo/*/__manifest__.py")
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(manifest_paths, do_exit=False, verbose=True)
        check_errors_keys = set()
        for check_errors in all_check_errors:
            check_errors_keys |= set(check_errors.keys())
        self.assertEqual(ALL_CHECKS, check_errors_keys)
