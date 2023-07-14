# pylint: disable=duplicate-code,useless-suppression
import glob
import os
import re
import subprocess
import sys
import unittest
from collections import defaultdict

import oca_pre_commit_hooks
from . import common

ALL_CHECK_CLASS = [
    oca_pre_commit_hooks.checks_odoo_module.ChecksOdooModule,
    oca_pre_commit_hooks.checks_odoo_module_csv.ChecksOdooModuleCSV,
    oca_pre_commit_hooks.checks_odoo_module_xml.ChecksOdooModuleXML,
]


EXPECTED_ERRORS = {
    "csv-duplicate-record-id": 1,
    "csv-syntax-error": 1,
    "manifest-syntax-error": 2,
    "xml-create-user-wo-reset-password": 1,
    "xml-dangerous-filter-wo-user": 1,
    "xml-dangerous-qweb-replace-low-priority": 9,
    "xml-deprecated-data-node": 8,
    "xml-deprecated-openerp-node": 4,
    "xml-deprecated-qweb-directive": 2,
    "xml-deprecated-tree-attribute": 3,
    "xml-duplicate-fields": 3,
    "xml-duplicate-record-id": 2,
    "xml-not-valid-char-link": 2,
    "xml-redundant-module-name": 1,
    "xml-syntax-error": 2,
    "xml-view-dangerous-replace-low-priority": 6,
    "xml-xpath-translatable-item": 4,
    "xml-oe-structure-missing-id": 6,
}


class TestChecksWithDirectories(common.ChecksCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        test_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo")
        cls.file_paths = glob.glob(os.path.join(test_repo_path, "*", "__openerp__.py")) + glob.glob(
            os.path.join(test_repo_path, "*", "__manifest__.py")
        )
        cls.file_paths = [os.path.dirname(i) for i in cls.file_paths]

    def setUp(self):
        super().setUp()
        self.checks_run = oca_pre_commit_hooks.checks_odoo_module.run
        self.checks_cli_main = oca_pre_commit_hooks.cli.main
        self.expected_errors = EXPECTED_ERRORS.copy()


class TestChecksWithFiles(common.ChecksCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        test_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo")
        cls.file_paths = glob.glob(os.path.join(test_repo_path, "*", "__openerp__.py")) + glob.glob(
            os.path.join(test_repo_path, "*", "__manifest__.py")
        )

    def setUp(self):
        super().setUp()
        self.checks_run = oca_pre_commit_hooks.checks_odoo_module.run
        self.checks_cli_main = oca_pre_commit_hooks.cli.main
        self.expected_errors = EXPECTED_ERRORS.copy()

    @unittest.skipIf(not os.environ.get("BUILD_README"), "BUILD_README environment variable not enabled")
    def test_build_docstring(self):

        # Run "tox -e update-readme"
        # Why this here?
        # The unittest are isolated using "tox" virtualenv with all test-requirements installed
        # and latest dev version of the package instead of using the
        # already installed in the OS (without latest dev changes)
        # and we do not have way to evaluate all checks are evaluated and documented from another side
        # Feel free to migrate to better place this non-standard section of the code

        checks_found, checks_docstring = oca_pre_commit_hooks.utils.get_checks_docstring(ALL_CHECK_CLASS)
        readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "README.md")
        with open(readme_path, encoding="UTF-8") as f_readme:
            readme_content = f_readme.read()

        checks_docstring = f"# Checks\n{checks_docstring}"
        new_readme = self.re_replace(
            "[//]: # (start-checks)", "[//]: # (end-checks)", checks_docstring, readme_content
        )

        # Find a better way to get the --help string
        help_content = subprocess.check_output(["oca-checks-odoo-module", "--help"], stderr=subprocess.STDOUT).decode(
            sys.stdout.encoding
        )
        help_content = f"# Help\n```bash\n{help_content}\n```"
        # remove extra spaces
        help_content = re.sub(r"\n(      )+", " ", help_content)
        help_content = re.sub(r"( )+", " ", help_content)
        new_readme = self.re_replace("[//]: # (start-help)", "[//]: # (end-help)", help_content, new_readme)

        all_check_errors = self.checks_run(sorted(self.file_paths), no_exit=True, no_verbose=False)

        all_check_errors_merged = defaultdict(list)
        for check_errors in all_check_errors:
            for check_error, msgs in check_errors.items():
                all_check_errors_merged[check_error].extend(msgs)

        version = oca_pre_commit_hooks.__version__
        check_example_content = ""
        for check_error, msgs in sorted(all_check_errors_merged.items(), key=lambda a: a[0]):
            check_example_content += f"\n\n * {check_error}\n"
            for msg in sorted(msgs):
                msg = msg.replace(":", "#L", 1)
                check_example_content += f"\n    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v{version}/{msg}"
        check_example_content = f"# Examples\n{check_example_content}"
        new_readme = self.re_replace(
            "[//]: # (start-example)", "[//]: # (end-example)", check_example_content, new_readme
        )
        with open(readme_path, "w", encoding="UTF-8") as f_readme:
            f_readme.write(new_readme)
        self.assertEqual(
            readme_content,
            new_readme,
            "The README was updated! Don't panic only failing for CI purposes. Run the same test again.",
        )
        self.assertFalse(set(self.expected_errors) - checks_found, "Missing docstring of checks tested")

    def test_non_exists_path(self):
        all_check_errors = self.checks_run(["/tmp/no_exists"], no_exit=True, no_verbose=False)
        self.assertFalse(all_check_errors)
