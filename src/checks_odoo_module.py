#!/usr/bin/env python3

# Hooks are using print directly
# pylint: disable=print-used

import ast
import os
import sys

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # no-qa
DFTL_README_FILES = ["README.rst", "README.md", "README.txt"]


def installable(method):
    def inner(self):
        msg_tmpl = "Skipped check '%s' module '%s'" % (method.__name__, self.odoo_addon_name)
        if self.odoo_addon_name == "absa":
            print(self.manifest_error)
        if self.manifest_error:
            print("%s with error: '%s'" % (msg_tmpl, self.manifest_error))
        elif not self.is_module_installable:
            print("%s is not installable" % (msg_tmpl))
        else:
            return method(self)

    return inner


class ChecksOdooModule:
    def __init__(self, manifest_path):
        self.manifest_path = os.path.relpath(manifest_path)
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.manifest_error = ""
        self.manifest_content = self._manifest_content()
        self.is_module_installable = self._is_module_installable()

    def _manifest_content(self):
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")) or not os.path.isfile(
            self.manifest_path
        ):
            return {}
        with open(self.manifest_path) as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            except BaseException as e:
                self.manifest_error = "Manifest %s with error %s" % (self.manifest_path, e)
        return {}

    def _is_module_installable(self):
        return self.manifest_content and self.manifest_content.get("installable", True)

    @installable
    def check_missing_readme(self):
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                return True
        print("Missing %s file. Template here: %s" % (DFTL_README_FILES[0], DFTL_README_TMPL_URL))
        return False

    def check_manifest(self):
        if not self.manifest_content:
            print("%s could not be loaded" % (self.manifest_path))
            return False


def main_missing_readme():
    global_res = True
    for fname in sys.argv[1:]:
        obj = ChecksOdooModule(fname)
        res = obj.check_missing_readme()
        if not res:
            global_res = False
        res = obj.check_manifest()
        if not res:
            global_res = False
    if not global_res:
        sys.exit(1)


def main():
    main_missing_readme()


if __name__ == "__main__":
    main()
