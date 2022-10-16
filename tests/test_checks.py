import glob
import unittest


import oca_pre_commit_hooks


class TestChecks(unittest.TestCase):
    def test_checks(self):
        manifest_paths = set(glob.glob("./test_repo/*/__openerp__.py") + glob.glob("./test_repo/*/__manifest__.py"))
        check_errors = oca_pre_commit_hooks.checks_odoo_module.run(manifest_paths, do_exit=False, verbose=False)
        check_errors_keys = check_errors.keys()
        # import pdb;pdb.set_trace()
        print("Hola mundo!")
