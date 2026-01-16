import libcst as cst
from fixit import CstLintRule, InvalidTestCase, ValidTestCase
from libcst.metadata import ParentNodeProvider, QualifiedName, QualifiedNameProvider

ODOO_BASES = {"Model", "TransientModel", "AbstractModel"}
ODOO_SUPER_CLASSES = (
    "odoo.models.AbstractModel",
    "odoo.models.Model",
    "odoo.models.TransientModel",
    "openerp.models.AbstractModel",
    "openerp.models.Model",
    "openerp.models.TransientModel",
)


class FieldStringRedundant(CstLintRule):
    """Detects and removes the 'string' parameter in odoo.fields if it is redundant
    (matches the field name in Title Case), ensuring it only applies to
    Odoo Class definitions (Models).
    """

    MESSAGE = "The 'string' attribute is redundant and should be removed."

    FIELD_STRING_POSITIONS = {
        "Selection": 1,
        "Reference": 1,
        "Many2one": 1,
        "One2many": 2,
        "Many2many": 1,
    }
    METADATA_DEPENDENCIES = (QualifiedNameProvider, ParentNodeProvider)

    def __init__(self) -> None:
        super().__init__()
        self.name = "field-string-redundant"
        self._is_inside_odoo_class = False
        self._is_inside_function = False

    def _is_odoo_model_inheritance(self, class_def: cst.ClassDef) -> bool:
        for base in class_def.bases:
            qnames = self.get_metadata(QualifiedNameProvider, base.value, set())
            for qname in qnames:
                if not isinstance(qname, QualifiedName):
                    continue
                name = qname.name
                if name.endswith(ODOO_SUPER_CLASSES):
                    return True
        return False

    def _get_sanitized_field_name(self, name: str) -> str:
        name = name.removesuffix("_ids").removesuffix("_id")
        return name.replace("_", " ").title()

    def visit_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: B906 pylint:disable=invalid-name
        if self._is_odoo_model_inheritance(node):
            self._is_inside_odoo_class = True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: B906 pylint:disable=invalid-name
        if self._is_inside_odoo_class:
            self._is_inside_odoo_class = False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: B906 pylint:disable=invalid-name
        self._is_inside_function = True

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: B906 pylint:disable=invalid-name
        self._is_inside_function = False

    def is_odoo_field_call(self, func: cst.Attribute) -> bool:
        if not isinstance(func.value, cst.Name):
            return False
        qnames = self.get_metadata(QualifiedNameProvider, func.value, set())
        for qname in qnames:
            if not isinstance(qname, QualifiedName):
                continue
            name = qname.name
            if "odoo.fields" in name or "openerp.fields" in name:
                return True
        return False

    def visit_Assign(self, node: cst.Assign) -> None:  # noqa: B906,C901 pylint:disable=invalid-name,too-complex
        if not self._is_inside_odoo_class or self._is_inside_function:
            return

        if len(node.targets) != 1:
            return
        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return

        field_variable_name = target.value
        call = node.value
        if not isinstance(call, cst.Call):
            return

        func = call.func
        if not self.is_odoo_field_call(func):
            return

        for arg in call.args:
            if arg.keyword and arg.keyword.value == "related":
                return

        field_type = func.attr.value
        string_arg_node = None

        for arg in call.args:
            if not arg.keyword:
                continue
            kw_value = arg.keyword.value
            if kw_value == "string":
                string_arg_node = arg
            elif kw_value == "related":
                # skip related fields since that the name change with the original one
                return

        if not string_arg_node:
            position = self.FIELD_STRING_POSITIONS.get(field_type, 0)
            if len(call.args) > position:
                candidate = call.args[position]
                if candidate.keyword is None and isinstance(candidate.value, cst.SimpleString):
                    string_arg_node = candidate

        if not string_arg_node:
            return

        if isinstance(string_arg_node.value, cst.SimpleString):
            raw_string = string_arg_node.value.value
            quote_char = raw_string[0]
            actual_string_value = raw_string.strip(quote_char)
        else:
            return

        sanitized_name = self._get_sanitized_field_name(field_variable_name)

        if actual_string_value == sanitized_name:
            new_args = [arg for arg in call.args if arg is not string_arg_node]
            new_call = call.with_changes(args=new_args)
            new_assign = node.with_changes(value=new_call)
            self.report(node, self.MESSAGE, replacement=new_assign)

    # --- Test Cases ---
    VALID = [
        ValidTestCase(
            """
            from odoo import fields, models
            class OrdinaryPythonClass:
                name = fields.Char(string='Name')
            """
        ),
        ValidTestCase(
            """
            from odoo import fields, models
            class MyModel(models.Model):
                def my_method(self):
                    name = fields.Char(string='Name')
            """
        ),
        ValidTestCase(
            """
            from odoo import fields, models
            class MyModel(models.Model):
                name = fields.Char()
                other = fields.Char(string='Different Label')
            """
        ),
        # not odoo.models
        ValidTestCase(
            """
            from odoo import fields
            class MyModel(models.Model):
                name = fields.Char('Name')
            """
        ),
        # not odoo.fields
        ValidTestCase(
            """
            from odoo import models
            class MyModel(models.Model):
                name = fields.Char('Name')
            """
        ),
        # ignore related fields
        ValidTestCase(
            """
            from odoo import fields, models
            class MyModel(models.Model):
                name33 = fields.Char('Name33', related="partner_id.name")
            """
        ),
    ]

    INVALID = [
        # --- Default Position 0 Types (Char, Text, Boolean, Integer, etc.) ---
        # Char: Positional
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                name = fields.Char('Name')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                name = fields.Char()
            """
            ),
        ),
        # Char: Keyword
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                name = fields.Char(string='Name', required=True)
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                name = fields.Char(required=True)
            """
            ),
        ),
        # Text
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                description = fields.Text(string='Description')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                description = fields.Text()
            """
            ),
        ),
        # Boolean
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                active = fields.Boolean("Active", default=True)
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                active = fields.Boolean(default=True)
            """
            ),
        ),
        # Integer
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                age = fields.Integer(string="Age")
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                age = fields.Integer()
            """
            ),
        ),
        # Float
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                score = fields.Float('Score')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                score = fields.Float()
            """
            ),
        ),
        # Html
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                body = fields.Html(string='Body')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                body = fields.Html()
            """
            ),
        ),
        # Date / Datetime
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                date_order = fields.Date(string='Date Order')
                create_date = fields.Datetime('Create Date')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                date_order = fields.Date()
                create_date = fields.Datetime()
            """
            ),
        ),
        # Monetary
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                amount = fields.Monetary(string="Amount")
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                amount = fields.Monetary()
            """
            ),
        ),
        # Binary
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                file_data = fields.Binary(string='File Data')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                file_data = fields.Binary()
            """
            ),
        ),
        # --- Position 1 Types (Selection, Reference, Many2one, Many2many) ---
        # Selection: Positional (selection, string)
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                state = fields.Selection([('a', 'A')], 'State')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                state = fields.Selection([('a', 'A')], )
            """
            ),
        ),
        # Selection: Keyword
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                type = fields.Selection(selection=[], string='Type')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                type = fields.Selection(selection=[], )
            """
            ),
        ),
        # Reference: Positional
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                res_id = fields.Reference([], 'Res')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                res_id = fields.Reference([], )
            """
            ),
        ),
        # Many2one: Positional
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                partner_id = fields.Many2one('res.partner', 'Partner')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                partner_id = fields.Many2one('res.partner', )
            """
            ),
        ),
        # Many2one: Keyword
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                user_id = fields.Many2one('res.users', string='User')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                user_id = fields.Many2one('res.users', )
            """
            ),
        ),
        # Many2many: Positional (comodel, string) -> A veces es pos 2 si lleva relation, pero lo común es 1
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                tag_ids = fields.Many2many('res.tag', 'Tag')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                tag_ids = fields.Many2many('res.tag', )
            """
            ),
        ),
        # --- Position 2 Types (One2many) ---
        # One2many: Positional (comodel, inverse, string)
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                line_ids = fields.One2many('my.line', 'link_id', 'Line')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                line_ids = fields.One2many('my.line', 'link_id', )
            """
            ),
        ),
        # One2many: Keyword
        InvalidTestCase(
            code=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                child_ids = fields.One2many('my.child', 'parent_id', string='Child')
            """
            ),
            expected_replacement=(
                """
            from odoo import fields, models
            class MyModel(models.Model):
                child_ids = fields.One2many('my.child', 'parent_id', )
            """
            ),
        ),
    ]
