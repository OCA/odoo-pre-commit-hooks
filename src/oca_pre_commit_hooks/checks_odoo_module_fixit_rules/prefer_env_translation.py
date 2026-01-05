import os

import libcst as cst
from fixit import InvalidTestCase, ValidTestCase
from libcst import matchers as m
from libcst.metadata import ParentNodeProvider, QualifiedName, QualifiedNameProvider

from .. import checks_odoo_module_fixit_common as common, utils

ODOO_SUPER_CLASSES = (
    "odoo.http.Controller",
    "odoo.models.AbstractModel",
    "odoo.models.Model",
    "odoo.models.TransientModel",
    "openerp.http.Controller",
    "openerp.models.AbstractModel",
    "openerp.models.Model",
    "openerp.models.TransientModel",
)

TRANSLATION_METHODS = ["odoo._", "openerp._", "odoo._lt", "openerp._lt"]


class OdooGettextFixer(cst.CSTTransformer):
    """Recursive fixer looking for calls and fixing them
    It helps when the line has multiple calls in the same line _(_(...))"""

    def __init__(self, func_name: str = "_"):
        self.func_name = func_name

    def leave_Call(  # noqa: B906 pylint:disable=invalid-name
        self, original_node: cst.Call, updated_node: cst.Call  # pylint:disable=unused-argument
    ) -> cst.Call:
        if m.matches(updated_node, m.Call(func=m.Name(value=self.func_name))):
            return updated_node.with_changes(
                func=cst.Attribute(
                    value=cst.Attribute(value=cst.Name("self"), attr=cst.Name("env")), attr=cst.Name("_")
                )
            )
        return updated_node


class PreferEnvTranslationRule(common.Common):
    """Replace `_('text')` with `self.env._('text')` only if '_' comes from 'odoo._'
    and only for modules >=18.0"""

    MESSAGE = "Use self.env._(...) instead of _(…) directly inside Odoo model methods."
    METADATA_DEPENDENCIES = (QualifiedNameProvider, ParentNodeProvider)

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
        ValidTestCase(
            code="""
    from odoo import _

    MAP = {
        "key1": lambda: _('No translatable from odoo models'),
    }
    # No Odoo models class
    class TestModel(object):
        def my_method(self):
            _("ok")
    """
        ),
        ValidTestCase(
            code="""
    from odoo import http, _ as lt


    class TestModel(http.Controller):
        @staticmethod
        def my_method():
            lt("old translated")
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
    from odoo import http, _ as lt


    class TestModel(http.Controller):
        def my_method(self):
            lt("old translated")
    """,
            expected_replacement="""
    from odoo import http, _ as lt


    class TestModel(http.Controller):
        def my_method(self):
            self.env._("old translated")
    """,
        ),
        InvalidTestCase(
            code="""
from odoo import http, _
from odoo.exceptions import ValidationError


class TestModel(http.Controller):
    def my_method(self):
        raise ValidationError(_(
            'The following numbers are already used:\\n%s',
            '\\n'.join(_(
                '%(n)s in journal %(j)s',
                n=_('n'),
                j=_('j'),
            ) for r in [])
        ))
    """,
            expected_replacement="""
from odoo import http, _
from odoo.exceptions import ValidationError


class TestModel(http.Controller):
    def my_method(self):
        raise ValidationError(self.env._(
            'The following numbers are already used:\\n%s',
            '\\n'.join(self.env._(
                '%(n)s in journal %(j)s',
                n=self.env._('n'),
                j=self.env._('j'),
            ) for r in [])
        ))
    """,
        ),
        InvalidTestCase(
            code="""
    from odoo import models, _lt
    class TestModel(models.Model):
        def my_method(self):
            _lt("old translated")
    """,
            expected_replacement="""
    from odoo import models, _lt
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
                f"It was not possible if {self.name} rule applies but even running "
                "To force a specific Odoo version, set the environment variable FIXIT_ODOO_VERSION=18.0"
            )
            self.odoo_version = self.odoo_min_version  # Set default min version to run the check
        if (
            not isinstance(node.func, cst.Name)
            or self.odoo_min_version > self.odoo_version
            or not (class_node := self._get_parent_class(node))
            or not self._is_odoo_model_or_controller(class_node)
            or not (func_node := self._get_parent_function(node))
            or not self._function_has_self(func_node)
        ):
            return
        for qname in self.get_metadata(QualifiedNameProvider, node.func, set()):
            if not isinstance(qname, QualifiedName) or qname.name not in TRANSLATION_METHODS:
                continue
            func_alias = node.func.value
            fixer = OdooGettextFixer(func_name=func_alias)
            replacement = node.visit(fixer)
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

    def _get_parent_class(self, node: cst.CSTNode) -> cst.ClassDef | None:
        parent = self.get_metadata(ParentNodeProvider, node, None)
        while parent:
            if isinstance(parent, cst.ClassDef):
                return parent
            parent = self.get_metadata(ParentNodeProvider, parent, None)
        return None

    def _is_odoo_model_or_controller(self, class_def: cst.ClassDef) -> bool:
        for base in class_def.bases:
            qnames = self.get_metadata(QualifiedNameProvider, base.value, set())
            for qname in qnames:
                if not isinstance(qname, QualifiedName):
                    continue
                name = qname.name
                if name.endswith(ODOO_SUPER_CLASSES):
                    return True
        return False

    def _get_parent_function(self, node: cst.CSTNode) -> cst.FunctionDef | None:
        """Look for the FunctionDef parent closest"""
        parent = self.get_metadata(ParentNodeProvider, node, None)
        while parent:
            if isinstance(parent, cst.FunctionDef):
                return parent
            if isinstance(parent, cst.ClassDef):
                # If there is not a method but class so it is an attribute
                return None
            parent = self.get_metadata(ParentNodeProvider, parent, None)
        return None

    def _function_has_self(self, func_node: cst.FunctionDef) -> bool:
        """Check the first argument is called 'self'"""
        params = func_node.params.params
        if not params:
            return False

        first_param = params[0]

        if isinstance(first_param.name, cst.Name) and first_param.name.value == "self":
            return True

        return False
