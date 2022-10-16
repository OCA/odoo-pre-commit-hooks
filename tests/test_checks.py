import glob
import unittest

import oca_pre_commit_hooks

ALL_CHECKS = [
    "xml_deprecated_openerp_xml_node",
    "xml_deprecated_qweb_directive",
    "xml_not_valid_char_link",
    "xml_create_user_wo_reset_password",
]


class TestChecks(unittest.TestCase):
    def test_checks(self):
        manifest_paths = glob.glob("./test_repo/*/__openerp__.py") + glob.glob("./test_repo/*/__manifest__.py")
        check_errors = oca_pre_commit_hooks.checks_odoo_module.run(manifest_paths, do_exit=False, verbose=False)
        check_errors_keys = list(check_errors.keys())
        self.assertEqual(ALL_CHECKS, check_errors_keys)
