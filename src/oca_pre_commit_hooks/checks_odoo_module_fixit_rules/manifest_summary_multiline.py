import ast
import os
import re

import libcst as cst
from fixit import InvalidTestCase, ValidTestCase

from .. import checks_odoo_module_fixit_common as common
from .. import utils


class ManifestSummaryMultiline(common.Common):
    """Ensure the manifest `summary` is a single-line short description.

    For Odoo 20.0+, multiline summaries are reported and can be autofixed by
    replacing newline separators with spaces.
    """

    MESSAGE = "Summary in manifest file should be a one-line short description, found newline character"

    VALID = [
        ValidTestCase(code="""
{
    'name': 'My Module',
    'summary': 'One line summary',
}
            """),
        ValidTestCase(code="""
{
    'name': 'My Module',
}
            """),
    ]

    INVALID = [
        InvalidTestCase(
            code="""
{
    'name': 'My Module',
    'summary': '''First line
    second line''',
}
            """,
            expected_replacement="""
{
    'name': 'My Module',
    'summary': 'First line second line',
}
            """,
        ),
        InvalidTestCase(
            code="""
{
    'name': 'My Module',
    'summary': 'First line\\nsecond line',
}
            """,
            expected_replacement="""
{
    'name': 'My Module',
    'summary': 'First line second line',
}
            """,
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.name = "manifest-summary-multiline"
        self.odoo_version = utils.str2version(os.getenv("FIXIT_ODOO_VERSION", ""))
        self.odoo_min_version = utils.str2version("20.0")

    @staticmethod
    def _evaluate_string(node: cst.BaseExpression) -> str | None:
        try:
            value = ast.literal_eval(cst.Module([]).code_for_node(node))
        except (SyntaxError, ValueError):
            return None
        return value if isinstance(value, str) else None

    @staticmethod
    def _normalize_summary(summary: str) -> str:
        return re.sub(r"\s*\n\s*", " ", summary).strip()

    @staticmethod
    def _get_manifest_dict(node: cst.Module) -> cst.Dict | None:
        if len(node.body) != 1:
            return None
        stmt = node.body[0]
        if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
            return None
        expr = stmt.body[0]
        if not isinstance(expr, cst.Expr) or not isinstance(expr.value, cst.Dict):
            return None
        return expr.value

    def visit_Module(self, node: cst.Module) -> None:  # pylint:disable=invalid-name
        if self.odoo_version is None or self.odoo_version < self.odoo_min_version:
            return
        if not (manifest_dict := self._get_manifest_dict(node)):
            return
        for element in manifest_dict.elements:
            if not isinstance(element, cst.DictElement):
                continue
            if not isinstance(element.key, cst.SimpleString) or element.key.evaluated_value != "summary":
                continue
            if not (summary := self._evaluate_string(element.value)) or "\n" not in summary:
                return
            self.report(
                element.value,
                self.MESSAGE,
                replacement=cst.parse_expression(repr(self._normalize_summary(summary))),
            )
            return
