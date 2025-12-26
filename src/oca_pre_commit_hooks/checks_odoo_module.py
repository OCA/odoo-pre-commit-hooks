#!/usr/bin/env python3
import ast
import glob
import os
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache
from itertools import chain
from pathlib import Path

from colorama import init as colorama_init
from fixit.api import fixit_paths
from fixit.config import collect_rules, parse_rule
from fixit.ftypes import Config, Options

from oca_pre_commit_hooks import checks_odoo_module_csv, checks_odoo_module_xml, utils
from oca_pre_commit_hooks.base_checker import BaseChecker

colorama_init(autoreset=True)

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "qweb", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")
MANIFEST_DATA_DIRS = [
    "data",
    "datas",
    "demo",
    "demos",
    "report",
    "reports",
    "security",
    "template",
    "templates",
    "view",
    "views",
    "wizard",
    "wizards",
]
MANIFEST_DATA_EXTS = [
    ".csv",
    ".xml",
]
DATA_MANUAL_KEY = "oca_data_manual"
BLUE_PILL = "\033[94m🔵\033[0m"
RED_PILL = "\033[91m🔴\033[0m"


class ChecksOdooModule(BaseChecker):
    def __init__(self, manifest_path, enable, disable, changed=None, verbose=True, autofix=False):
        super().__init__(enable, disable, autofix=autofix, module_version=utils.manifest_version(manifest_path))
        if not os.path.isfile(manifest_path) or os.path.basename(manifest_path) not in MANIFEST_NAMES:
            raise UserWarning(  # pragma: no cover
                f"Not valid manifest file name {manifest_path} file expected {MANIFEST_NAMES}"
            )
        self.manifest_path = manifest_path
        self.changed = changed if changed is not None else []
        self.verbose = verbose
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.manifest_top_path = utils.top_path(self.odoo_addon_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.checks_errors = []

    def _manifest2dict(self):
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            if self.verbose:
                print(f"[bold]{self.manifest_path}[/bold]: missing `__init__.py` file")
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

    def _glob_expr2filenames(self, data_section):
        """Support new way of odoo to add assets
        e.g. odoo/addons/spreadsheet_dashboard/__manifest__.py
        "assets": {
            "web.assets_backend": [
                "spreadsheet_dashboard/static/src/assets/**/*.js"

        It will return the following format:
            ['static/src/assets/path1/file1.js']
        Only if the module is the same
        """
        fnames = []
        data_section_value = self.manifest_dict.get(data_section)
        if isinstance(data_section_value, dict):
            fname_glob_lists = self.manifest_dict[data_section].values()
        elif isinstance(data_section_value, list):
            fname_glob_lists = [data_section_value]
        else:
            fname_glob_lists = []
        for fname_glob_list in fname_glob_lists:
            for fname_glob in fname_glob_list:
                if not isinstance(fname_glob, str):
                    continue
                if data_section == "qweb":
                    fname_glob = os.path.join(os.path.basename(self.odoo_addon_path), fname_glob)
                with utils.chdir(os.path.dirname(self.odoo_addon_path)):
                    for fname in glob.glob(fname_glob):
                        if not fname.startswith(self.odoo_addon_name):
                            continue
                        fname = os.path.relpath(fname, os.path.basename(self.odoo_addon_path))
                        fnames.append(fname)
        return fnames

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)
        for data_section in DFTL_MANIFEST_DATA_KEYS + ["assets", "po"]:
            if data_section in ["assets", "qweb"]:
                # support glob expression
                manifest_fnames = self._glob_expr2filenames(data_section)
            elif data_section == "po":
                # The i18n[_extra]/*.po[t] files are not defined in the manifest
                manifest_fnames = glob.glob(os.path.join(self.odoo_addon_path, "i18n*", "*.po")) + glob.glob(
                    os.path.join(self.odoo_addon_path, "i18n*", "*.pot")
                )
            else:
                manifest_fnames = self.manifest_dict.get(data_section) or []
            for fname in manifest_fnames:
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
        return ext_referenced_files

    @utils.only_required_for_checks("manifest-syntax-error")
    def check_manifest(self):
        """* Check manifest-syntax-error
        Check if the manifest file has syntax error
        """
        if not self.manifest_dict:
            manifest_path_short = os.path.relpath(self.manifest_path, self.manifest_top_path)
            self.register_error(
                code="manifest-syntax-error",
                message="Manifest could not be loaded",
                info=self.error,
                filepath=manifest_path_short,
                line=1,
            )

    @staticmethod
    def _get_module_data_files(module_root_path):
        module_root_path_obj = Path(module_root_path).resolve()
        fnames = set()
        for subpath_obj in module_root_path_obj.rglob("*"):
            parts = subpath_obj.relative_to(module_root_path_obj).parts
            if (
                not subpath_obj.is_file()  # is file
                or len(parts) != 2  # only depth 2
                or parts[0].lower() not in MANIFEST_DATA_DIRS  # only valid dir
                or subpath_obj.suffix.lower() not in MANIFEST_DATA_EXTS  # only valid ext
            ):
                continue
            fnames.add(subpath_obj.relative_to(module_root_path_obj).as_posix())
        return fnames

    @utils.only_required_for_installable()
    @utils.only_required_for_checks("file-not-used")
    def check_file_not_used(self):
        """* Check file-not-used
        Check if there is a file created but not referenced from __manifest__.py
        """
        manifest_files = set()
        for _ext, manifest_referenced_files in self.manifest_referenced_files.items():
            for manifest_referenced_file in manifest_referenced_files:
                filename_obj = Path(manifest_referenced_file["filename"]).resolve()
                manifest_files.add(filename_obj.relative_to(self.odoo_addon_path).as_posix())
        addon_files = self._get_module_data_files(self.odoo_addon_path)
        manifest_path_short = os.path.relpath(self.manifest_path, self.manifest_top_path)
        manual_files = self.manifest_dict.get(DATA_MANUAL_KEY) or []
        for file_not_used in addon_files - manifest_files:
            if file_not_used in manual_files:
                # Ignore data files imported manually
                # e.g. Imported from "post_init_hook" script instead of __manifest__.py "data" key
                continue
            file_not_used_short = os.path.join(self.odoo_addon_name, file_not_used)
            self.register_error(
                code="file-not-used",
                message=f'File "{file_not_used_short}" is not referenced in the manifest.',
                info=(
                    f"{RED_PILL} If it is loaded from another source (e.g. a post_init_hook script),"
                    " just add it under the section "
                    f'"{DATA_MANUAL_KEY}": ["{file_not_used}",] to be considered. '
                    f"{BLUE_PILL} Otherwise, you might want to remove it."
                ),
                filepath=manifest_path_short,
                line=1,
            )

    @utils.only_required_for_installable()
    @utils.only_required_for_checks("prefer-readme-rst")
    def check_readme(self):
        """* Check prefer-readme-rst
        Check if the module has README.md file to prefer README.rst file
        """
        if self.is_message_enabled("prefer-readme-rst"):
            readme_md = Path(self.odoo_addon_path) / "README.md"
            if readme_md.is_file():
                manifest_path_short = readme_md.relative_to(self.manifest_top_path)
                self.register_error(
                    code="prefer-readme-rst",
                    message="Prefer README.rst instead of README.md",
                    info=self.error,
                    filepath=str(manifest_path_short),
                    line=1,
                )
                if self.autofix:
                    subprocess.check_output(
                        ["git", "mv", str(manifest_path_short), str(manifest_path_short.with_suffix(".rst"))],
                        cwd=self.manifest_top_path,
                        stderr=subprocess.STDOUT,
                    )

    @utils.only_required_for_installable()
    def check_xml(self):
        manifest_datas = self.manifest_referenced_files[".xml"]
        if not manifest_datas:
            return
        checks_obj = checks_odoo_module_xml.ChecksOdooModuleXML(
            manifest_datas,
            self.odoo_addon_name,
            self.enable,
            self.disable,
            module_version=self.module_version,
            autofix=self.autofix,
        )
        for check_meth in utils.getattr_checks(checks_obj):
            check_meth()
        self.checks_errors.extend(checks_obj.checks_errors)

    @utils.only_required_for_installable()
    def check_csv(self):
        manifest_datas = self.manifest_referenced_files[".csv"]
        if not manifest_datas:  # pragma: no cover
            return
        checks_obj = checks_odoo_module_csv.ChecksOdooModuleCSV(
            manifest_datas, self.odoo_addon_name, self.enable, self.disable
        )
        for check_meth in utils.getattr_checks(checks_obj):
            check_meth()
        self.checks_errors.extend(checks_obj.checks_errors)

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_fixit_rules(manifest_rule):
        rule = parse_rule(".checks_odoo_module_fixit", Path(os.path.dirname(os.path.abspath(__file__))))
        lint_rules = collect_rules(Config(enable=[rule], disable=[], python_version=None))
        return [
            (
                parse_rule(
                    f"{lint_rule.__module__.replace('fixit.local', '')}",
                    Path(os.path.dirname(os.path.abspath(__file__))),
                ),
                lint_rule.name,
            )
            for lint_rule in lint_rules
            if (
                manifest_rule
                and lint_rule.name.startswith("manifest-")
                or not manifest_rule
                and not lint_rule.name.startswith("manifest-")
            )
        ]

    def _get_fixit_enabled_rules(self, manifest_rule):
        lint_rules = self._get_fixit_rules(manifest_rule)
        return [lint_rule for lint_rule, lint_rule_name in lint_rules if self.is_message_enabled(lint_rule_name)]

    @utils.only_required_for_installable()
    def check_py(self):
        """Run fixit"""
        os.environ["FIXIT_ODOO_VERSION"] = str(self.module_version) or os.getenv("VERSION") or "18.0"
        os.environ["FIXIT_AUTOFIX"] = str(self.autofix)
        lint_rules_enabled_all = self._get_fixit_enabled_rules(manifest_rule=False)
        lint_rules_enabled_manifest = self._get_fixit_enabled_rules(manifest_rule=True)
        if not (lint_rules_enabled_all or lint_rules_enabled_manifest):
            return
        results = []
        if lint_rules_enabled_manifest:
            manifest_options = Options(debug=False, output_format="vscode", rules=lint_rules_enabled_manifest)
            results.append(
                fixit_paths(
                    paths=[Path(self.manifest_path)],
                    options=manifest_options,
                    autofix=self.autofix,
                    parallel=False,
                )
            )
        if lint_rules_enabled_all:
            all_options = Options(debug=False, output_format="vscode", rules=lint_rules_enabled_all)
            results.append(
                fixit_paths(
                    paths=[Path(self.odoo_addon_path)],
                    options=all_options,
                    autofix=self.autofix,
                    parallel=False,
                )
            )
        for result in chain.from_iterable(results):
            if not result.violation:
                continue
            message = result.violation.message
            if result.violation.autofixable and not self.autofix:
                message += " (has autofix)"
            filename_short = os.path.relpath(result.path.as_posix(), self.manifest_top_path)
            self.register_error(
                code=result.violation.rule_name,
                message=message,
                info=(self.error or "")
                + (
                    "You can disable this check by adding the following comment to the "
                    f"affected line or just above it `# lint-ignore: {result.violation.rule_name}`"
                ),
                filepath=filename_short,
                line=result.violation.range.start.line,
                column=result.violation.range.start.column,
            )


def lookup_manifest_paths(filenames_or_modules):
    """Look for manifest path for "filenames_or_modules" paths
    walking up in parent paths
    Return a dictionary with {manifest_path: filename_or_module} items
    """
    odoo_module_files_changed = defaultdict(set)
    # Sorted in order to re-use the LRU cached values as possible before to fill maxsize
    # Ordered paths will have common ancestors closed to next item
    for filename_or_module in sorted(filenames_or_modules):
        filename_or_module = utils.full_norm_path(filename_or_module)
        directory_path = (
            os.path.dirname(filename_or_module) if os.path.isfile(filename_or_module) else filename_or_module
        )
        manifest_path = utils.walk_up(directory_path, MANIFEST_NAMES, utils.top_path(directory_path))
        odoo_module_files_changed[manifest_path].add(filename_or_module)
    return odoo_module_files_changed


def run(files_or_modules, enable=None, disable=None, no_verbose=False, no_exit=False, list_msgs=False, autofix=False):
    if list_msgs:
        _, checks_docstring = utils.get_checks_docstring(
            [ChecksOdooModule, checks_odoo_module_csv.ChecksOdooModuleCSV, checks_odoo_module_xml.ChecksOdooModuleXML]
        )
        if not no_verbose:
            print("Emittable messages with the current interpreter:", end="")
            print(checks_docstring)
        if no_exit:
            return checks_docstring
        sys.exit(0)

    all_check_errors = []
    # TODO: Add unnitest to check files filtered from pre-commit by hook
    # Uncommet to check what files sent pre-commit
    # open("/tmp/borrar.txt", "w").write(f"{len(files_or_modules)}\n{files_or_modules}")
    if enable is None:
        enable = set()
    if disable is None:
        disable = set()
    exit_status = 0
    for manifest_path, changed in lookup_manifest_paths(files_or_modules).items():
        if not manifest_path:
            continue
        checks_obj = ChecksOdooModule(
            os.path.realpath(manifest_path), enable, disable, changed=changed, verbose=not no_verbose, autofix=autofix
        )
        for check in utils.getattr_checks(checks_obj):
            check()
        if checks_obj.checks_errors:
            all_check_errors.extend(checks_obj.checks_errors)
            exit_status = 1
    # Sort errors by filepath, line, column and code
    all_check_errors.sort()
    # Print errors
    if not no_verbose:
        for error in all_check_errors:
            print(error)
            print("")
    if no_exit:
        return all_check_errors
    sys.exit(exit_status)


def main(**kwargs):
    return run(**kwargs)


if __name__ == "__main__":
    main()
