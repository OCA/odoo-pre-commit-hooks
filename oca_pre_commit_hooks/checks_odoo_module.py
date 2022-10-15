#!/usr/bin/env python3

# Hooks are using print directly
# pylint: disable=print-used

import ast
import os
import sys
from collections import defaultdict

from oca_pre_commit_hooks import checks_odoo_module_xml, tools

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


def installable(method):
    def inner(self):
        msg_tmpl = "Skipped check '%s' for '%s'" % (
            method.__name__,
            self.manifest_path,
        )
        if self.error:
            print("%s with error: '%s'" % (msg_tmpl, self.error))
        elif not self.is_module_installable:
            print("%s is not installable" % (msg_tmpl))
        else:
            return method(self)

    return inner


class ChecksOdooModule:
    # TODO: Support check by version
    # TODO: skip_files_ext skip check based on comment XML
    # TODO: Support configuration file to set custom value for DFTL_ global variables
    # TODO: Use relative path for name of files in msg check
    #       e.g. os.path.relpath(record.base, pwd)
    # TODO: Add autofix option and autofix the files
    def __init__(self, manifest_path):
        self.manifest_path = self._get_manifest_file_path(manifest_path)
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.checks_errors = defaultdict(list)

    def _get_manifest_file_path(self, original_manifest_path):
        for manifest_name in MANIFEST_NAMES:
            manifest_path = os.path.join(original_manifest_path, manifest_name)
            if os.path.isfile(manifest_path):
                return manifest_path
        return original_manifest_path

    def _manifest2dict(self):
        if os.path.basename(
            self.manifest_path
        ) not in MANIFEST_NAMES or not os.path.isfile(self.manifest_path):
            print("The path %s is not %s file" % (self.manifest_path, MANIFEST_NAMES))
            return {}
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            print("The path %s does not have __init__.py file" % self.manifest_path)
            return {}
        with open(self.manifest_path) as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            except BaseException as e:  # Using same way than odoo
                self.error = "Manifest %s with error %s" % (
                    self.manifest_path,
                    e,
                )
        return {}

    def _is_installable(self):
        return self.manifest_dict and self.manifest_dict.get("installable", True)

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)
        for data_section in DFTL_MANIFEST_DATA_KEYS:
            for fname in self.manifest_dict.get(data_section) or []:
                ext_referenced_files[os.path.splitext(fname)[1].lower()].append(
                    {
                        "filename": os.path.realpath(
                            os.path.join(self.odoo_addon_path, os.path.normpath(fname))
                        ),
                        "filename_short": os.path.normpath(fname),
                        "data_section": data_section,
                    }
                )
        return ext_referenced_files

    def check_manifest(self):
        if not self.manifest_dict:
            self.checks_errors["check_manifest"].append(
                f"{self.manifest_path} could not be loaded"
            )

    @installable
    def check_missing_readme(self):
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                return
        self.checks_errors["missing_readme"].append(
            f"{readme_path} missed file. Template here: {DFTL_README_TMPL_URL}"
        )

    @installable
    def check_xml(self):
        checks_xml_obj = checks_odoo_module_xml.ChecksOdooModuleXML(
            self.manifest_referenced_files[".xml"], self.odoo_addon_name
        )
        for check_xml_meth in tools.getattr_checks(checks_xml_obj):
            check_xml_meth()
        self.checks_errors.update(checks_xml_obj.checks_errors)


def main(do_exit=True):
    tools.main(ChecksOdooModule, sys.argv[1:], do_exit=do_exit)


if __name__ == "__main__":
    main()
