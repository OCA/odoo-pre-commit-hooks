import os

import libcst as cst
from fixit import InvalidTestCase, ValidTestCase
from libcst.metadata import QualifiedName, QualifiedNameProvider

from .. import checks_odoo_module_fixit_common as common, utils


class PreferEnvTranslationRule(common.Common):
    """Replace `_('text')` with `self.env._('text')` only if '_' comes from 'odoo._'
    and only for modules >=18.0"""

    MESSAGE = "Use self.env._(...) instead of _(…) directly inside Odoo model methods."
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    VALID = [
        ValidTestCase(
            code="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            self.env._("ok")
    """
        ),
        ValidTestCase(
            code="""
    from gettext import gettext as _


    def outside_model():
        _("not Odoo")
    """
        ),
        ValidTestCase(
            code="""
    _ = lambda *a: True


    class TestModel(models.Model):
        def my_method(self):
            _("is not a Odoo translation")
    """
        ),
    ]

    INVALID = [
        InvalidTestCase(
            code="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            _("old translated")
    """,
            expected_replacement="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            self.env._("old translated")
    """,
        ),
        InvalidTestCase(
            code="""
    from odoo import models, _ as lt


    class TestModel(models.Model):
        def my_method(self):
            lt("old translated")
    """,
            expected_replacement="""
    from odoo import models, _ as lt


    class TestModel(models.Model):
        def my_method(self):
            self.env._("old translated")
    """,
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.name = "prefer-env-translation"
        self.odoo_version = utils.str2version(os.getenv("FIXIT_ODOO_VERSION", ""))
        self.odoo_min_version = utils.str2version("18.0")

    def visit_Call(self, node: cst.Call) -> None:  # noqa: B906 pylint:disable=invalid-name
        if not self.odoo_version:
            print(
                f"WARNING. Invalid manifest versions format ({self.odoo_version}). "
                f"It was not possible if {self.name} rule applies but even running",
            )
            self.odoo_version = self.odoo_min_version  # Set default min version to run the check
        if not isinstance(node.func, cst.Name):
            return
        if self.odoo_min_version > self.odoo_version:
            return
        qualified_names = self.get_metadata(QualifiedNameProvider, node.func, set())
        for qname in qualified_names:
            if isinstance(qname, QualifiedName) and (
                qname.name.startswith("odoo._") or qname.name.startswith("openerp._")
            ):
                replacement = self.fix(node)
                self.report(node, replacement=replacement)
                break

    def fix(self, node: cst.Call) -> cst.Call:
        return node.with_changes(
            func=cst.Attribute(
                value=cst.Attribute(
                    value=cst.Name("self"),
                    attr=cst.Name("env"),
                ),
                attr=cst.Name("_"),
            )
        )
