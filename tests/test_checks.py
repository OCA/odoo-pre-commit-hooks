# pylint: disable=duplicate-code,useless-suppression
import glob
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

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
    "file-not-used": 1,
    "manifest-superfluous-key": 3,
    "manifest-syntax-error": 2,
    "prefer-env-translation": 41,
    "prefer-readme-rst": 1,
    "unused-logger": 1,
    "xml-create-user-wo-reset-password": 1,
    "xml-dangerous-qweb-replace-low-priority": 9,
    "xml-deprecated-data-node": 8,
    "xml-deprecated-openerp-node": 4,
    "xml-deprecated-qweb-directive": 2,
    "xml-deprecated-tree-attribute": 3,
    "xml-duplicate-fields": 3,
    "xml-duplicate-record-id": 2,
    "xml-not-valid-char-link": 2,
    "xml-redundant-module-name": 3,
    "xml-syntax-error": 2,
    "xml-template-prettier-incompatible": 3,
    "xml-view-dangerous-replace-low-priority": 7,
    "xml-xpath-translatable-item": 4,
    "xml-oe-structure-missing-id": 6,
    "xml-record-missing-id": 2,
    "xml-duplicate-template-id": 9,
    "xml-header-missing": 2,
    "xml-header-wrong": 18,
    "xml-id-position-first": 9,
    "xml-deprecated-oe-chatter": 1,
    "xml-field-bool-without-eval": 2,
    "xml-field-numeric-without-eval": 7,
}


class TestChecks(common.ChecksCommon):

    def setUp(self):
        super().setUp()
        self.file_paths = glob.glob(os.path.join(self.test_repo_path, "*", "__openerp__.py")) + glob.glob(
            os.path.join(self.test_repo_path, "*", "__manifest__.py")
        )
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
        all_check_errors_by_code = self.get_grouped_errors(all_check_errors)

        version = oca_pre_commit_hooks.__version__
        check_example_content = ""
        for code in sorted(all_check_errors_by_code):
            check_example_content += f"\n\n * {code}\n"
            for check_error in sorted(all_check_errors_by_code[code])[:3]:
                msg = f"{check_error.position.filepath}"
                if check_error.position.line:
                    msg += f"#L{check_error.position.line}"
                if check_error.message:
                    msg += f" {check_error.message}"
                check_example_content += (
                    f"\n    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v{version}/test_repo/{msg}"
                )
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

    def test_autofix(self):
        # Before autofix
        fname_wo_header = os.path.join(self.test_repo_path, "broken_module", "xml_wo_header.xml")
        with open(fname_wo_header, "rb") as f_wo_header:
            content = f_wo_header.read()
        self.assertFalse(content.strip().startswith(b"<?xml version="), "The XML header was previously added")

        fname_wrong_header = os.path.join(self.test_repo_path, "broken_module", "model_view.xml")
        with open(fname_wrong_header, "rb") as f_wrong_header:
            content = f_wrong_header.read()
        self.assertFalse(
            content.strip().startswith(oca_pre_commit_hooks.checks_odoo_module_xml.XML_HEADER_EXPECTED),
            "The XML wrong header was previously fixed",
        )

        fname_wrong_xmlid_order = os.path.join(self.test_repo_path, "broken_module", "model_view_odoo2.xml")
        with open(fname_wrong_xmlid_order, "rb") as f_wrong_xmlid_order:
            content = f_wrong_xmlid_order.read()
        self.assertIn(
            b'<record model="ir.ui.view" id="view_ir_config_search">',
            content,
            "The XML wrong xmlid order was previously fixed",
        )
        self.assertIn(
            b"<menuitem name=\"Root\" id='broken_module.menu_root' />",
            content,
            "The XML wrong xmlid order and redundant module name was previously fixed",
        )
        self.assertIn(
            b"<menuitem name=\"Root 2\"\n        id='broken_module.menu_root2'",
            content,
            "The XML wrong xmlid order and redundant module name was previously fixed",
        )

        fname_wrong_xml_eval = os.path.join(self.test_repo_path, "broken_module", "demo", "duplicated_id_demo.xml")
        with open(fname_wrong_xml_eval, "rb") as f_wrong_xml_eval:
            content = f_wrong_xml_eval.read()
        self.assertIn(
            b'<field name="active">True</field>',
            content,
            "The XML eval was previously fixed",
        )
        self.assertIn(
            b'<field name="sequence">1</field>',
            content,
            "The XML eval was previously fixed",
        )
        self.assertIn(
            b'<field name="amount">1.08</field>',
            content,
            "The XML eval was previously fixed",
        )
        self.assertIn(
            b'<field name="phone">4777777777</field>',
            content,
            "The XML eval was previously fixed",
        )
        self.assertIn(
            b'<field name="priority">-1</field>',
            content,
            "The XML eval was not fixed",
        )

        fname_redundant_module_name = os.path.join(self.test_repo_path, "broken_module", "model_view2.xml")
        with open(fname_redundant_module_name, "rb") as f_redundant_module_name:
            content = f_redundant_module_name.read()
        self.assertIn(
            b'<record id="broken_module.view_model_form2" model="ir.ui.view">',
            content,
            "The XML wrong redundant module name was previously fixed",
        )
        self.assertTrue(
            (Path(self.test_repo_path) / "broken_module" / "README.md").is_file(),
            "The README.md file should exist before autofix",
        )
        self.assertFalse(
            (Path(self.test_repo_path) / "broken_module" / "README.rst").is_file(),
            "The README.rst file should not exist before autofix",
        )

        template_xml = os.path.join(self.test_repo_path, "test_module", "website_templates.xml")
        with open(template_xml, "rb") as f_template_xml:
            content = f_template_xml.read()
        self.assertIn(
            b'''<template
        name="test_module_widget"
        inherit_id="web.assets_backend"
        id="assets_backend"''',
            content,
            "The XML wrong xmlid order was previously fixed",
        )

        self.assertIn(
            b"""<template
        name='test_module_widget_2'
        inherit_id="web.assets_backend"
        id='assets_backend_2'
    />""",
            content,
            "The XML wrong xmlid order was previously fixed",
        )

        self.checks_run(self.file_paths, autofix=True, no_exit=True, no_verbose=False)

        # After autofix
        with open(fname_wo_header, "rb") as f_wo_header:
            content = f_wo_header.read()
        self.assertTrue(content.strip().startswith(b"<?xml version="), "The XML header was not added")

        with open(fname_wrong_header, "rb") as f_wrong_header:
            content = f_wrong_header.read()
        self.assertTrue(
            content.strip().startswith(oca_pre_commit_hooks.checks_odoo_module_xml.XML_HEADER_EXPECTED),
            "The XML wrong header was not fixed",
        )
        with open(fname_wrong_xmlid_order, "rb") as f_wrong_xmlid_order:
            content = f_wrong_xmlid_order.read()
        self.assertIn(
            b'<record id="view_ir_config_search" model="ir.ui.view">', content, "The XML wrong xmlid was not fixed"
        )
        self.assertIn(
            b"<menuitem id='menu_root' name=\"Root\" />",
            content,
            "The XML wrong xmlid order and redundant module name was not fixed",
        )
        self.assertIn(
            b"<menuitem id='menu_root2'\n        name=\"Root 2\"",
            content,
            "The XML wrong xmlid order multiline and redundant module name was not fixed",
        )

        with open(fname_wrong_xml_eval, "rb") as f_wrong_xml_eval:
            content = f_wrong_xml_eval.read()
        self.assertIn(
            b'<field name="active" eval="True" />',
            content,
            "The XML eval was not fixed",
        )
        self.assertIn(
            b'<field name="sequence" eval="1" />',
            content,
            "The XML eval was not fixed",
        )
        self.assertIn(
            b'<field name="priority" eval="-1" />',
            content,
            "The XML eval was not fixed",
        )
        self.assertIn(
            b'<field name="amount">1.08</field>',
            content,
            "The XML eval was not should be fixed for amount in that model",
        )
        self.assertIn(
            b'<field name="phone">4777777777</field>',
            content,
            "The XML eval was not should be fixed for phone numbers",
        )

        with open(fname_redundant_module_name, "rb") as f_redundant_module_name:
            content = f_redundant_module_name.read()
        self.assertIn(
            b'<record id="view_model_form2" model="ir.ui.view">',
            content,
            "The XML wrong redundant module name was not fixed",
        )
        self.assertFalse(
            (Path(self.test_repo_path) / "broken_module" / "README.md").is_file(),
            "The README.md file should not exist after autofix",
        )
        self.assertTrue(
            (Path(self.test_repo_path) / "broken_module" / "README.rst").is_file(),
            "The README.rst file should exist after autofix",
        )

        with open(template_xml, "rb") as f_template_xml:
            content = f_template_xml.read()
        self.assertIn(
            b'''<template
        id="assets_backend"
        name="test_module_widget"
        inherit_id="web.assets_backend"''',
            content,
            "The XML xmlid order was not fixed",
        )
        self.assertIn(
            b"""<template
        id='assets_backend_2'
        name='test_module_widget_2'
        inherit_id="web.assets_backend"
    />""",
            content,
            "The XML xmlid order was not fixed",
        )
