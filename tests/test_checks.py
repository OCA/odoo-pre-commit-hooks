import glob
import os
import re
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from itertools import chain

import oca_pre_commit_hooks

ALL_CHECK_CLASS = [
    oca_pre_commit_hooks.checks_odoo_module.ChecksOdooModule,
    oca_pre_commit_hooks.checks_odoo_module_csv.ChecksOdooModuleCSV,
    oca_pre_commit_hooks.checks_odoo_module_po.ChecksOdooModulePO,
    oca_pre_commit_hooks.checks_odoo_module_xml.ChecksOdooModuleXML,
]

EXPECTED_ERRORS = {
    "csv_duplicate_record_id": 1,
    "csv_syntax_error": 1,
    "manifest_syntax_error": 2,
    "missing_readme": 2,
    "po_duplicate_message_definition": 3,
    "po_python_parse_format": 4,
    "po_python_parse_printf": 2,
    "po_requires_module": 1,
    "po_syntax_error": 1,
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
    # TODO: Test modules without CSV or XML or PO

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        test_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo")
        cls.manifest_paths = glob.glob(os.path.join(test_repo_path, "*", "__openerp__.py")) + glob.glob(
            os.path.join(test_repo_path, "*", "__manifest__.py")
        )
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

    def assertDictEqual(self, d1, d2, msg=None):
        """Original method does not show the correct item diff
        Using ordered list it is showing the diff better"""
        real_dict2list = [(i, d1[i]) for i in sorted(d1)]
        expected_dict2list = [(i, d2[i]) for i in sorted(d2)]
        self.assertEqual(real_dict2list, expected_dict2list, msg)

    def test_checks(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
            self.manifest_paths, no_exit=True, no_verbose=False
        )
        real_errors = self.get_count_code_errors(all_check_errors)
        # Uncommet to get sorted values to update EXPECTED_ERRORS dict
        # print('\n'.join(f"'{key}':{count_code_errors[key]}," for key in sorted(count_code_errors)))
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_checks_with_cli(self):
        sys.argv = ["", "--no-exit", "--no-verbose"] + self.module_paths
        all_check_errors = oca_pre_commit_hooks.cli.main()
        real_errors = self.get_count_code_errors(all_check_errors)
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_non_exists_path(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
            ["/tmp/no_exists"], no_exit=True, no_verbose=True
        )
        check_errors_keys = self.get_all_code_errors(all_check_errors)
        self.assertEqual({"manifest_syntax_error"}, check_errors_keys)

    def test_checks_hook(self):
        # TODO: Autogenerate .pre-commit-config-local.yaml from .pre-commit-config.yaml
        # TODO: Run subprocess compatible with dynamic_context of coverage
        cmd = ["pre-commit", "run", "--config=.pre-commit-config-local.yaml", "-v", "--all", "--color=never"]
        try:
            returncode = 0
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as process_error:
            returncode = process_error.returncode
            output = process_error.output
        output = output.decode(sys.stdout.encoding)
        self.assertTrue(returncode, f"The process exited with code zero {returncode} {output}")
        checks_found = re.findall(r"\- \[(?P<check>\w+)\]", output)

        real_errors = dict(Counter(checks_found))
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_checks_disable(self):
        checks_disabled = {
            "xml_syntax_error",
            "xml_redundant_module_name",
            "csv_duplicate_record_id",
            "po_duplicate_message_definition",
            "missing_readme",
        }
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
            self.manifest_paths, no_exit=True, no_verbose=True, disable=checks_disabled
        )
        real_errors = self.get_count_code_errors(all_check_errors)
        for check_disabled in checks_disabled:
            self.expected_errors.pop(check_disabled, False)
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_checks_disable_one_by_one(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
                self.manifest_paths, no_exit=True, no_verbose=True, disable={check2disable}
            )
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            self.assertDictEqual(real_errors, expected_errors)

    def test_checks_disable_with_cli(self):
        checks_disabled = {
            "xml_syntax_error",
            "xml_redundant_module_name",
            "csv_duplicate_record_id",
            "po_duplicate_message_definition",
            "missing_readme",
        }
        sys.argv = ["", "--no-exit", "--no-verbose", f"--disable={','.join(checks_disabled)}"] + self.module_paths
        all_check_errors = oca_pre_commit_hooks.cli.main()
        real_errors = self.get_count_code_errors(all_check_errors)
        for check_disabled in checks_disabled:
            self.expected_errors.pop(check_disabled, False)
        self.assertDictEqual(real_errors, self.expected_errors)

    def test_checks_disable_one_by_one_with_cli(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            sys.argv = ["", "--no-exit", "--no-verbose", f"--disable={check2disable}"] + self.module_paths
            all_check_errors = oca_pre_commit_hooks.cli.main()
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            self.assertDictEqual(real_errors, expected_errors)

    def test_checks_enable_one_by_one(self):
        for check2enable in self.expected_errors:
            all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
                self.manifest_paths, no_exit=True, no_verbose=True, enable={check2enable}
            )
            real_errors = self.get_count_code_errors(all_check_errors)
            self.assertDictEqual(real_errors, {check2enable: self.expected_errors[check2enable]})

    def test_checks_enable_one_by_one_with_cli(self):
        for check2enable in self.expected_errors:
            sys.argv = ["", "--no-exit", "--no-verbose", f"--enable={check2enable}"] + self.module_paths
            all_check_errors = oca_pre_commit_hooks.cli.main()
            real_errors = self.get_count_code_errors(all_check_errors)
            self.assertDictEqual(real_errors, {check2enable: self.expected_errors[check2enable]})

    def test_build_docstring(self):
        checks_docstring = ""
        checks_found = set()
        for check_class in ALL_CHECK_CLASS:
            for check_meth in chain(
                oca_pre_commit_hooks.utils.getattr_checks(check_class, prefix="visit"),
                oca_pre_commit_hooks.utils.getattr_checks(check_class, prefix="check"),
            ):
                if not check_meth or not check_meth.__doc__ or "* Check" not in check_meth.__doc__:
                    continue
                checks_docstring += "\n" + check_meth.__doc__.strip(" \n") + "\n"
                re_check = r"\* Check (?P<check>\w+)"
                checks_found |= set(re.findall(re_check, checks_docstring))
                checks_docstring = re.sub(r"( )+\*", "*", checks_docstring)
        if os.environ.get("BUILD_README"):
            checks_docstring = f"[//]: # (start-checks)\n# Checks\n{checks_docstring}\n[//]: # (end-checks)"
            readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "README.md")
            with open(readme_path, "r+", encoding="UTF-8") as f_readme:
                readme_content = f_readme.read()
                f_readme.seek(0)
                readme_with_checks_docstring = re.compile(
                    r"\[//\]:\ \#\ \(start\-checks\).*^.*\(end\-checks\)", re.M | re.S
                ).sub(checks_docstring, readme_content)
                f_readme.write(readme_with_checks_docstring)
        self.assertFalse(set(self.expected_errors) - checks_found, "Missing docstring of checks tested")
