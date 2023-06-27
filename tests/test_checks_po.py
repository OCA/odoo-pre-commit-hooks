import glob
import os
import re
import subprocess
import sys
import unittest
from collections import defaultdict
from shutil import copyfile
from tempfile import TemporaryDirectory

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
    "po-pretty-format": 6,
}


class TestChecksPO(common.ChecksCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo")
        po_glob_pattern = os.path.join(cls.test_repo_path, "**", "*.po")
        pot_glob_pattern = f"{po_glob_pattern}t"
        cls.file_paths = glob.glob(po_glob_pattern, recursive=True) + glob.glob(pot_glob_pattern, recursive=True)

    def setUp(self):
        super().setUp()
        self.expected_errors = EXPECTED_ERRORS.copy()
        self.checks_run = oca_pre_commit_hooks.checks_odoo_module_po.run
        self.checks_cli_main = oca_pre_commit_hooks.cli_po.main

    def test_non_exists_path(self):
        all_check_errors = self.checks_run(["/tmp/no_exists"], no_exit=True, no_verbose=False)
        real_errors = self.get_count_code_errors(all_check_errors)
        self.assertDictEqual(real_errors, {"po-syntax-error": 1})

    def test_pretty_format_po(self):
        ugly_po = os.path.join(self.test_repo_path, "eleven_module", "i18n", "ugly.po")
        pretty_po = os.path.join(self.test_repo_path, "eleven_module", "i18n", "pretty.po")

        errors = self.checks_run([pretty_po], enable={"po-pretty-format"}, no_exit=True, no_verbose=False)
        self.assertFalse(errors)

        errors = self.checks_run([ugly_po], enable={"po-pretty-format"}, no_exit=True, no_verbose=False)
        self.assertIn("po-pretty-format", errors[0])

    @unittest.skipIf(
        sys.platform.startswith("win"), "tmpdir may be created in a different disk, breaking relative paths"
    )
    def test_pretty_format_po_autofix(self):
        ugly_po = os.path.join(self.test_repo_path, "eleven_module", "i18n", "ugly.po")
        autofix_po = os.path.join(self.test_repo_path, "eleven_module", "i18n", "autofixed_ugly.po")

        with TemporaryDirectory() as tmpdir:
            ugly_po_cp = os.path.join(tmpdir, "ugly.po")
            copyfile(ugly_po, ugly_po_cp)

            self.checks_run([ugly_po_cp], enable={"po-pretty-format"}, no_exit=True, no_verbose=False, autofix=False)
            with open(ugly_po_cp, encoding="utf-8") as ugly_fd, open(autofix_po, encoding="utf-8") as pretty_fd:
                self.assertNotEqual(ugly_fd.read(), pretty_fd.read())

            self.checks_run([ugly_po_cp], enable={"po-pretty-format"}, no_exit=True, no_verbose=False, autofix=True)
            with open(ugly_po_cp, encoding="utf-8") as ugly_fd, open(autofix_po, encoding="utf-8") as pretty_fd:
                self.assertEqual(ugly_fd.read(), pretty_fd.read())

    @unittest.skipIf(not os.environ.get("BUILD_README"), "BUILD_README environment variable not enabled")
    def test_build_docstring(self):

        checks_found, checks_docstring = oca_pre_commit_hooks.utils.get_checks_docstring(
            [oca_pre_commit_hooks.checks_odoo_module_po.ChecksOdooModulePO]
        )

        readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "README.md")
        with open(readme_path, encoding="UTF-8") as f_readme:
            readme_content = f_readme.read()

        checks_docstring = f"# Checks PO\n{checks_docstring}"
        new_readme = self.re_replace(
            "[//]: # (start-checks-po)", "[//]: # (end-checks-po)", checks_docstring, readme_content
        )

        # Find a better way to get the --help string
        help_content = subprocess.check_output(["oca-checks-po", "--help"], stderr=subprocess.STDOUT).decode(
            sys.stdout.encoding
        )
        help_content = f"# Help PO\n```bash\n{help_content}\n```"
        # remove extra spaces
        help_content = re.sub(r"\n(      )+", " ", help_content)
        help_content = re.sub(r"( )+", " ", help_content)
        new_readme = self.re_replace("[//]: # (start-help-po)", "[//]: # (end-help-po)", help_content, new_readme)

        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=False)

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
        check_example_content = f"# Examples PO\n{check_example_content}"
        new_readme = self.re_replace(
            "[//]: # (start-example-po)", "[//]: # (end-example-po)", check_example_content, new_readme
        )
        with open(readme_path, "w", encoding="UTF-8") as f_readme:
            f_readme.write(new_readme)
        self.assertEqual(
            readme_content,
            new_readme,
            "The README was updated! Don't panic only failing for CI purposes. Run the same test again.",
        )

        self.assertFalse(set(self.expected_errors) - checks_found, "Missing docstring of checks tested")
