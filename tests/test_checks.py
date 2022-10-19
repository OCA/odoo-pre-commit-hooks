import glob
import os
import re
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from itertools import chain

import oca_pre_commit_hooks

RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"
RE_CHECK_OUTPUT = r"\- \[(?P<check>[\w|-]+)\]"

ALL_CHECK_CLASS = [
    oca_pre_commit_hooks.checks_odoo_module.ChecksOdooModule,
    oca_pre_commit_hooks.checks_odoo_module_csv.ChecksOdooModuleCSV,
    oca_pre_commit_hooks.checks_odoo_module_po.ChecksOdooModulePO,
    oca_pre_commit_hooks.checks_odoo_module_xml.ChecksOdooModuleXML,
]

EXPECTED_ERRORS = {
    "csv-duplicate-record-id": 1,
    "csv-syntax-error": 1,
    "manifest-syntax-error": 2,
    "missing-readme": 2,
    "po-duplicate-message-definition": 3,
    "po-python-parse-format": 4,
    "po-python-parse-printf": 2,
    "po-requires-module": 1,
    "po-syntax-error": 1,
    "xml-create-user-wo-reset-password": 1,
    "xml-dangerous-filter-wo-user": 1,
    "xml-dangerous-qweb-replace-low-priority": 3,
    "xml-deprecated-data-node": 8,
    "xml-deprecated-openerp-xml-node": 5,
    "xml-deprecated-qweb-directive": 2,
    "xml-deprecated-tree-attribute": 3,
    "xml-duplicate-fields": 9,
    "xml-duplicate-record-id": 3,
    "xml-not-valid-char-link": 2,
    "xml-redundant-module-name": 1,
    "xml-syntax-error": 2,
    "xml-view-dangerous-replace-low-priority": 6,
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
            ["/tmp/no_exists"], no_exit=True, no_verbose=False
        )
        self.assertFalse(all_check_errors)

    def test_checks_hook(self):
        # TODO: Autogenerate .pre-commit-config-local.yaml from .pre-commit-config.yaml
        # TODO: Run subprocess compatible with dynamic_context of coverage
        cmd = ["pre-commit", "run", "-avc", ".pre-commit-config-local.yaml", "--color=never"]
        try:
            returncode = 0
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as process_error:
            returncode = process_error.returncode
            output = process_error.output
        output = output.decode(sys.stdout.encoding)
        self.assertTrue(returncode, f"The process exited with code zero {returncode} {output}")
        checks_found = re.findall(RE_CHECK_OUTPUT, output)

        real_errors = dict(Counter(checks_found))
        self.assertDictEqual(real_errors, self.expected_errors, output)

    def test_checks_disable(self):
        checks_disabled = {
            "xml-syntax-error",
            "xml-redundant-module-name",
            "csv-duplicate-record-id",
            "po-duplicate-message-definition",
            "missing-readme",
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
            "xml-syntax-error",
            "xml-redundant-module-name",
            "csv-duplicate-record-id",
            "po-duplicate-message-definition",
            "missing-readme",
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

    @staticmethod
    def re_replace(sub_start, sub_end, substitution, content):
        re_sub = re.compile(rf"${re.escape(sub_start)}^.*${re.escape(sub_end)}^", re.M | re.S)
        new_content = re_sub.sub(f"{sub_start}\n{substitution}\n{sub_end}", content)
        return new_content

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
                checks_found |= set(re.findall(RE_CHECK_DOCSTRING, checks_docstring))
                checks_docstring = re.sub(r"( )+\*", "*", checks_docstring)
        if os.environ.get("BUILD_README"):
            # Run "tox -e update-readme"
            # Why this here?
            # The unittest are isolated using "tox" virtualenv with all test-requirements installed
            # and latest dev version of the package instead of using the
            # already installed in the OS (without latest dev changes)
            # and we do not have way to evaluate all checks are evaluated and documented from another side
            # Feel free to migrate to better place this non-standard section of the code

            # checks_docstring = f"[//]: # (start-checks)\n# Checks\n{checks_docstring}\n[//]: # (end-checks)"
            checks_docstring = f"# Checks\n{checks_docstring}"
            readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "README.md")
            with open(readme_path, "r+", encoding="UTF-8") as f_readme:
                readme_content = f_readme.read()

                new_readme = self.re_replace(
                    "[//]: # (start-checks)", "[//]: # (end-checks)", checks_docstring, readme_content
                )

                # Find a better way to get the --help string
                help_content = subprocess.check_output(
                    ["oca-checks-odoo-module", "--help"], stderr=subprocess.STDOUT
                ).decode(sys.stdout.encoding)
                help_content = f"# Help\n```bash\n{help_content}\n```"
                new_readme = self.re_replace("[//]: # (start-help)", "[//]: # (end-help)", help_content, new_readme)

                all_check_errors = oca_pre_commit_hooks.checks_odoo_module.run(
                    self.manifest_paths, no_exit=True, no_verbose=False
                )

                version = oca_pre_commit_hooks.__version__
                check_example_content = ""
                for check_errors in all_check_errors:
                    for check_error, msgs in check_errors.items():
                        check_example_content += f"\n\n * {check_error}\n"
                        for msg in msgs:
                            msg = msg.replace(":", "#L", 1)
                            check_example_content += (
                                f"\n    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v{version}/{msg}"
                            )

                check_example_content = f"# Examples\n{check_example_content}"
                new_readme = self.re_replace("[//]: # (start-help)", "[//]: # (end-help)", help_content, new_readme)

                f_readme.seek(0)
                f_readme.write(new_readme)
            self.assertEqual(readme_content, new_readme)

        self.assertFalse(set(self.expected_errors) - checks_found, "Missing docstring of checks tested")
