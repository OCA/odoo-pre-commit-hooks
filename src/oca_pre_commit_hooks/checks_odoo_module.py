#!/usr/bin/env python3
import ast
import glob
import os
import subprocess
import sys
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from oca_pre_commit_hooks import checks_odoo_module_csv, checks_odoo_module_po, checks_odoo_module_xml, utils

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


class ChecksOdooModule:
    # TODO: Support check by version
    # TODO: skip_files_ext skip check based on comment XML
    # TODO: Support configuration file to set custom value for DFTL_ global variables
    # TODO: Add autofix option and autofix the files
    # TODO: ir.model.access.csv:5 Duplicate csv record ... in ir.model.access.csv:6
    #       Use ir.model.access.csv:5 Duplicate csv record ... in line 6
    # TODO: Process only the changed if it is defined: set(changed) & set(manifest_data + README + po)
    # TODO: Use current directory for filename_short if it is not related with the repo
    def __init__(self, manifest_path, enable, disable, changed=None, verbose=True):
        if not os.path.isfile(manifest_path) or os.path.basename(manifest_path) not in MANIFEST_NAMES:
            raise UserWarning(  # pragma: no cover
                f"Not valid manifest file name {manifest_path} file expected {MANIFEST_NAMES}"
            )
        self.manifest_path = manifest_path
        self.changed = changed if changed is not None else []
        self.enable = enable
        self.disable = disable
        self.verbose = verbose
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.manifest_top_path = top_path(self.odoo_addon_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.checks_errors = defaultdict(list)

    def _manifest2dict(self):
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            self.print(f"The path {self.manifest_path} does not have __init__.py file")
            return {}
        with open(self.manifest_path, "r", encoding="UTF-8") as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            # Using same way than odoo
            except BaseException:  # pylint: disable=broad-except
                # Not use "exception error" string because it return mutable memory numbers
                self.error = "manifest malformed"
        return {}

    def _is_installable(self):
        return self.manifest_dict and self.manifest_dict.get("installable", True)

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)
        for data_section in DFTL_MANIFEST_DATA_KEYS:
            for fname in self.manifest_dict.get(data_section) or []:
                fname_path = os.path.join(self.odoo_addon_path, fname)
                ext_referenced_files[os.path.splitext(fname)[1].lower()].append(
                    {
                        "filename": fname_path,
                        "filename_short": os.path.relpath(fname_path, self.manifest_top_path),
                        "data_section": data_section,
                    }
                )
        # The i18n[_extra]/*.po[t] files are not defined in the manifest
        fnames = glob.glob(os.path.join(self.odoo_addon_path, "i18n*", "*.po")) + glob.glob(
            os.path.join(self.odoo_addon_path, "i18n*", "*.pot")
        )
        for fname in fnames:
            fname_path = os.path.join(self.odoo_addon_path, fname)
            ext_referenced_files[os.path.splitext(fname)[1].lower()].append(
                {
                    "filename": fname_path,
                    "filename_short": os.path.relpath(fname_path, self.manifest_top_path),
                    "data_section": "default",
                }
            )
        return ext_referenced_files

    @utils.only_required_for_checks("manifest-syntax-error")
    def check_manifest(self):
        """* Check manifest-syntax-error
        Check if the manifest file has syntax error
        """
        if not self.manifest_dict:
            manifest_path_short = os.path.relpath(self.manifest_path, self.manifest_top_path)
            self.checks_errors["manifest-syntax-error"].append(
                f"{manifest_path_short}:1 could not be loaded {self.error}".strip()
            )

    @utils.only_required_for_installable()
    @utils.only_required_for_checks("missing-readme")
    def check_missing_readme(self):
        """* Check missing-readme
        Check if a README file is missing"""
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                return
        readme_path_short = os.path.relpath(readme_path, self.manifest_top_path)
        self.checks_errors["missing-readme"].append(
            f"{readme_path_short}:1 missed file. Template here: {DFTL_README_TMPL_URL}"
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


def full_norm_path(path):
    """Expand paths in all possible ways"""
    return os.path.normpath(os.path.realpath(os.path.abspath(os.path.expanduser(os.path.expandvars(path.strip())))))


@lru_cache(maxsize=256)
def walk_up(path, filenames, top):
    """Look for "filenames" walking up in parent paths of "path"
    but limited only to "top" path
    """
    if full_norm_path(path) == full_norm_path(top):
        return None
    for filename in filenames:
        path_filename = os.path.join(path, filename)
        if os.path.isfile(full_norm_path(path_filename)):
            return path_filename
    return walk_up(os.path.dirname(path), filenames, top)


@lru_cache(maxsize=256)
def top_path(path):
    """Get the top level path based on git
    But if it is not a git repository so the top is the drive name
    e.g. / or C:\\

    It is using lru_cache in order to re-use top level path values
    if multiple files are sharing the same path
    """
    try:
        with chdir(path):
            return subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode(sys.stdout.encoding).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        path = Path(path)
        return path.root or path.drive


@contextmanager
def chdir(directory):
    """Change the current directory similar to command 'cd directory'
    but remembering the previous value to be revert at final
    Similar to run 'original_dir=$(pwd) && cd odoo && cd ${original_dir}'
    """
    original_dir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(original_dir)


def lookup_manifest_paths(filenames_or_modules):
    """Look for manifest path for "filenames_or_modules" paths
    walking up in parent paths
    Return a dictionary with {manifest_path: filename_or_module} items
    """
    odoo_module_files_changed = defaultdict(set)
    # Sorted in order to re-use the LRU cached values as possible before to fill maxsize
    # Ordered paths will have common ascentors closed to next item
    for filename_or_module in sorted(filenames_or_modules):
        filename_or_module = full_norm_path(filename_or_module)
        directory_path = (
            os.path.dirname(filename_or_module) if os.path.isfile(filename_or_module) else filename_or_module
        )
        manifest_path = walk_up(directory_path, MANIFEST_NAMES, top_path(directory_path))
        odoo_module_files_changed[manifest_path].add(filename_or_module)
    return odoo_module_files_changed


def run(filenames_or_modules, enable=None, disable=None, no_verbose=False, no_exit=False):
    all_check_errors = []
    for manifest_path, changed in lookup_manifest_paths(filenames_or_modules).items():
        if not manifest_path:
            continue
        checks_obj = ChecksOdooModule(
            os.path.realpath(manifest_path), enable, disable, changed=changed, verbose=not no_verbose
        )
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
