import glob
import os
import re
import subprocess
import sys
from itertools import chain

import oca_pre_commit_hooks
from . import common

RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"

ALL_CHECK_CLASS = [
    oca_pre_commit_hooks.checks_odoo_module.ChecksOdooModule,
    oca_pre_commit_hooks.checks_odoo_module_csv.ChecksOdooModuleCSV,
    oca_pre_commit_hooks.checks_odoo_module_xml.ChecksOdooModuleXML,
]

EXPECTED_ERRORS = {
    "csv-duplicate-record-id": 1,
    "csv-syntax-error": 1,
    "manifest-syntax-error": 2,
    "missing-readme": 2,
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

                all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=False)

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
                new_readme = self.re_replace(
                    "[//]: # (start-example)", "[//]: # (end-example)", check_example_content, new_readme
                )

                f_readme.seek(0)
                f_readme.write(new_readme)
            self.assertEqual(
                readme_content, new_readme, "The README was updated! Don't panic only failing for CI purposes."
            )

        self.assertFalse(set(self.expected_errors) - checks_found, "Missing docstring of checks tested")

    def test_non_exists_path(self):
        all_check_errors = self.checks_run(["/tmp/no_exists"], no_exit=True, no_verbose=False)
        self.assertFalse(all_check_errors)
