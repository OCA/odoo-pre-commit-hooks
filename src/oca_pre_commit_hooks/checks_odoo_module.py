#!/usr/bin/env python3
import ast
import glob
import os
import sys
from collections import defaultdict

from oca_pre_commit_hooks import checks_odoo_module_csv, checks_odoo_module_xml, utils

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
        self.manifest_top_path = utils.top_path(self.odoo_addon_path)
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
        with open(self.manifest_path, encoding="UTF-8") as f_manifest:
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
                value = {
                    "filename": fname_path,
                    "filename_short": os.path.relpath(fname_path, self.manifest_top_path),
                    "data_section": data_section,
                }
                ext = os.path.splitext(fname)[1].lower()
                if value in ext_referenced_files[ext]:
                    # Duplicated files will be skipped in order to avoid detecting duplicated xmlids
                    # pylint will take care about this check error
                    continue
                ext_referenced_files[ext].append(value)
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

    def print(self, object2print):
        if not self.verbose:
            return
        print(object2print)


def lookup_manifest_paths(filenames_or_modules):
    """Look for manifest path for "filenames_or_modules" paths
    walking up in parent paths
    Return a dictionary with {manifest_path: filename_or_module} items
    """
    odoo_module_files_changed = defaultdict(set)
    # Sorted in order to re-use the LRU cached values as possible before to fill maxsize
    # Ordered paths will have common ascentors closed to next item
    for filename_or_module in sorted(filenames_or_modules):
        filename_or_module = utils.full_norm_path(filename_or_module)
        directory_path = (
            os.path.dirname(filename_or_module) if os.path.isfile(filename_or_module) else filename_or_module
        )
        manifest_path = utils.walk_up(directory_path, MANIFEST_NAMES, utils.top_path(directory_path))
        odoo_module_files_changed[manifest_path].add(filename_or_module)
    return odoo_module_files_changed


def run(files_or_modules, enable=None, disable=None, no_verbose=False, no_exit=False):
    all_check_errors = []
    # TODO: Add unnitest to check files filtered from pre-commit by hook
    # Uncommet to check what files sent pre-commit
    # open("/tmp/borrar.txt", "w").write(f"{len(files_or_modules)}\n{files_or_modules}")
    for manifest_path, changed in lookup_manifest_paths(files_or_modules).items():
        if not manifest_path:
            continue
        checks_obj = ChecksOdooModule(
            os.path.realpath(manifest_path), enable, disable, changed=changed, verbose=not no_verbose
        )
        for check in utils.getattr_checks(checks_obj, enable=enable, disable=disable):
            check()
        utils.filter_checks_enabled_disabled(checks_obj.checks_errors, enable, disable)
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
