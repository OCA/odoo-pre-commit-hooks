import unittest

import oca_pre_commit_hooks


class TestChecks(unittest.TestCase):
    def test_checks(self):
        check_errors = oca_pre_commit_hooks.checks_odoo_module.run(["test_repo"], do_exit=False, verbose=False)
        print("Hola mundo!")
