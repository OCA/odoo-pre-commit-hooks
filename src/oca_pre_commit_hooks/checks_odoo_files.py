#!/usr/bin/env python3
import os
import sys

from oca_pre_commit_hooks import checks_odoo_module_csv, checks_odoo_module_xml, utils
from oca_pre_commit_hooks.base_checker import BaseChecker

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "qweb", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


class ChecksOdooFiles(BaseChecker):
    def __init__(self, path, enable, disable, verbose=False, autofix=False, autofix_char=None):
        super().__init__(enable, disable, autofix=autofix)
        self.path = path
        self.verbose = verbose
        if self.autofix:
            if autofix_char is None:
                self.autofix_char = "_"
            elif autofix_char in "/\\.: ":
                self.print(f"Illegal autofix_char {autofix_char} changed to _")
                self.autofix_char = "_"
            else:
                self.autofix_char = autofix_char

    def _prepend_path(self, path, files):
        return [(path, f) for f in files]

    def _perform_autofix(self, path, file):
        new_name = file.replace(" ", self.autofix_char)
        tentative_name = new_name
        i = 1
        while os.path.isfile(os.path.join(path, tentative_name)):
            root, ext = os.path.splitext(new_name)
            tentative_name = f"{root}_{i}{ext}"
            i += 1
        self.print('File ' + os.path.join(path, file) + ' renamed to ' + os.path.join(path, tentative_name))
        os.rename(os.path.join(path, file), os.path.join(path, tentative_name))

    def check_filename_spaces(self):
        """Checks sape-in-filename
        Checks if the filename has spaces
        """
        if os.path.isdir(self.path):
            
            file_list = sum(
                [self._prepend_path(path, files) for path, _, files in os.walk(self.path)],
                []
            )

            for path, file in file_list:
                if ' ' in file:
                    self.checks_errors["space-in-filename"].append(
                        f"file {file} has a space in its name"
                    )
                    if self.autofix:
                        self._perform_autofix(path, file)
        else:
            self.print(f"Directory {self.path} does not exist")

    def print(self, object2print):
        if not self.verbose:
            return
        print(object2print)


def run(paths, enable=None, disable=None, no_verbose=False, no_exit=False, list_msgs=False, autofix=False, autofix_char=None):
    if list_msgs:
        _, checks_docstring = utils.get_checks_docstring(
            [ChecksOdooFiles, checks_odoo_module_csv.ChecksOdooModuleCSV, checks_odoo_module_xml.ChecksOdooModuleXML]
        )
        if not no_verbose:
            print("Emittable messages with the current interpreter:", end="")
            print(checks_docstring)
        if no_exit:
            return checks_docstring
        sys.exit(0)

    all_check_errors = []
    if enable is None:
        enable = set()
    if disable is None:
        disable = set()
    exit_status = 0
    for path in paths:
        checks_obj = ChecksOdooFiles(
            path, enable, disable, verbose=not no_verbose, autofix=autofix, autofix_char=autofix_char
        )
        for check in utils.getattr_checks(checks_obj):
            check()
        if checks_obj.checks_errors:
            all_check_errors.append(checks_obj.checks_errors)
            exit_status = 1
        for check_error, msgs in checks_obj.checks_errors.items() if not no_verbose else {}:
            checks_obj.print(f"\n****{check_error}****")
            for msg in msgs:
                checks_obj.print(f"{msg} - [{check_error}]")
    if no_exit:
        return all_check_errors
    sys.exit(exit_status)


def main(**kwargs):
    return run(**kwargs)


if __name__ == "__main__":
    main()
