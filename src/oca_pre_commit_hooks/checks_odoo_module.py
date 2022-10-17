#!/usr/bin/env python3

import ast
import glob
import os
import sys
from collections import defaultdict

from oca_pre_commit_hooks import checks_odoo_module_csv, checks_odoo_module_po, checks_odoo_module_xml, utils

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


class ChecksOdooModule:
    # TODO: Support check by version
    # TODO: skip_files_ext skip check based on comment XML
    # TODO: Support configuration file to set custom value for DFTL_ global variables
    # TODO: Use relative path for name of files in msg check
    #       e.g. os.path.relpath(record.base, pwd)
    # TODO: Add autofix option and autofix the files
    # TODO: ir.model.access.csv:5 Duplicate csv record ... in ir.model.access.csv:6
    #       Use ir.model.access.csv:5 Duplicate csv record ... in line 6
    def __init__(self, manifest_path, enable, disable, verbose=True):
        self.manifest_path = self._get_manifest_file_path(manifest_path)
        self.enable = enable
        self.disable = disable
        self.verbose = verbose
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.checks_errors = defaultdict(list)

    @staticmethod
    def _get_manifest_file_path(original_manifest_path):
        for manifest_name in MANIFEST_NAMES:
            manifest_path = os.path.join(original_manifest_path, manifest_name)
            if os.path.isfile(manifest_path):
                return manifest_path
        return original_manifest_path

    def _manifest2dict(self):
        if os.path.basename(self.manifest_path) not in MANIFEST_NAMES or not os.path.isfile(self.manifest_path):
            self.print(f"The path {self.manifest_path} is not {MANIFEST_NAMES} file")
            return {}
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            self.print(f"The path {self.manifest_path} does not have __init__.py file")
            return {}
        with open(self.manifest_path, "r", encoding="UTF-8") as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            # Using same way than odoo
            except BaseException as err:  # pylint: disable=broad-except
                self.error = f"Manifest {self.manifest_path} with error {err}"
        return {}

    def _is_installable(self):
        return self.manifest_dict and self.manifest_dict.get("installable", True)

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)
        for data_section in DFTL_MANIFEST_DATA_KEYS:
            for fname in self.manifest_dict.get(data_section) or []:
                ext_referenced_files[os.path.splitext(fname)[1].lower()].append(
                    {
                        "filename": os.path.realpath(os.path.join(self.odoo_addon_path, os.path.normpath(fname))),
                        "filename_short": os.path.normpath(fname),
                        "data_section": data_section,
                    }
                )
        # The i18n[_extra]/*.po[t] files are not defined in the manifest
        fnames = glob.glob(os.path.join(self.odoo_addon_path, "i18n*", "*.po")) + glob.glob(
            os.path.join(self.odoo_addon_path, "i18n*", "*.pot")
        )
        for fname in fnames:
            ext_referenced_files[os.path.splitext(fname)[1].lower()].append(
                {
                    "filename": os.path.realpath(os.path.join(self.odoo_addon_path, os.path.normpath(fname))),
                    "filename_short": os.path.normpath(fname),
                    "data_section": "default",
                }
            )
        return ext_referenced_files

    @utils.only_required_for_checks("manifest_syntax_error")
    def check_manifest(self):
        """* Check manifest_syntax_error
        Check if the manifest file has syntax error
        """
        if not self.manifest_dict:
            self.checks_errors["manifest_syntax_error"].append(
                f"{self.manifest_path} could not be loaded {self.error}"
            )

    @utils.only_required_for_installable()
    @utils.only_required_for_checks("missing_readme")
    def check_missing_readme(self):
        """* Check missing_readme
        Check if a README file is missing"""
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                return
        self.checks_errors["missing_readme"].append(
            f"{readme_path} missed file. Template here: {DFTL_README_TMPL_URL}"
        )

    @utils.only_required_for_installable()
    def check_xml(self):
        manifest_datas = self.manifest_referenced_files[".xml"]
        if not manifest_datas:
            return
        checks_obj = checks_odoo_module_xml.ChecksOdooModuleXML(
            manifest_datas, self.odoo_addon_name, self.enable, self.disable
        )
        for check_meth in utils.getattr_checks(checks_obj, self.enable, self.disable):
            check_meth()
        self.checks_errors.update(checks_obj.checks_errors)

    @utils.only_required_for_installable()
    def check_csv(self):
        manifest_datas = self.manifest_referenced_files[".csv"]
        if not manifest_datas:  # pragma: no cover
            return
        checks_obj = checks_odoo_module_csv.ChecksOdooModuleCSV(
            manifest_datas, self.odoo_addon_name, self.enable, self.disable
        )
        for check_meth in utils.getattr_checks(checks_obj, self.enable, self.disable):
            check_meth()
        self.checks_errors.update(checks_obj.checks_errors)

    @utils.only_required_for_installable()
    def check_po(self):
        manifest_datas = self.manifest_referenced_files[".po"] + self.manifest_referenced_files[".pot"]
        if not manifest_datas:
            return
        checks_obj = checks_odoo_module_po.ChecksOdooModulePO(
            manifest_datas, self.odoo_addon_name, self.enable, self.disable
        )
        for check_meth in utils.getattr_checks(checks_obj, self.enable, self.disable):
            check_meth()
        self.checks_errors.update(checks_obj.checks_errors)

    def print(self, object2print):
        if not self.verbose:
            return
        print(object2print)  # pylint: disable=print-used

    def filter_checks_enabled_disabled(self):
        """Remove disabled checks from "check_errors" dictionary
        It is needed since that there are checks called without option to disable them
        e.g. syntax error checks

        Remove checks not enabled only if enabled was defined
        """
        if not self.checks_errors:
            return
        for disable in self.disable or []:
            self.checks_errors.pop(disable, False)
        if not self.enable:
            return
        checks_no_enable = set(self.checks_errors) - self.enable
        for check_no_enable in checks_no_enable:
            self.checks_errors.pop(check_no_enable, False)


def run(filenames_or_modules, enable=None, disable=None, no_verbose=False, no_exit=False):
    all_check_errors = []
    for manifest_path in filenames_or_modules:
        checks_obj = ChecksOdooModule(os.path.realpath(manifest_path), enable, disable, verbose=not no_verbose)
        for check in utils.getattr_checks(checks_obj, enable=enable, disable=disable):
            check()
        checks_obj.filter_checks_enabled_disabled()
        all_check_errors.append(checks_obj.checks_errors)
    for check_errors in all_check_errors if not no_verbose else []:
        for check_error, msgs in check_errors.items():
            checks_obj.print(f"\n****{check_error}****")
            for msg in msgs:
                checks_obj.print(f"{msg} - [{check_error}]")
    if no_exit:
        return all_check_errors
    sys.exit(bool(all_check_errors))


def main(**kwargs):
    return run(**kwargs)


if __name__ == "__main__":
    main()
