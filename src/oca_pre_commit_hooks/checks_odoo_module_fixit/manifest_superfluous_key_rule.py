import libcst as cst
from fixit import InvalidTestCase, ValidTestCase

from .. import checks_odoo_module_fixit_common as common


class ManifestSuperfluousKeyRule(common.Common):
    """Identifies and removes
    Identifies from Odoo manifest files (__manifest__.py) superfluous keys
    (if they have the same as the default value) should be omitted for simplicity

    e.g. 'installable': True
    `True` is the default value for installable key

    e.g. 'data': []
    `[]` is the default value for 'data' key
    """

    INVALID = [
        InvalidTestCase(
            code="""
{
    'installable': True,
    'depends': [],
    'author': '',
    'name': 'My Module',
}
    """,
            expected_replacement="""
{
    'name': 'My Module',
}
    """,
        ),
        InvalidTestCase(
            code="""
{
    'installable': True,
    'name': 'Another Module',
}
    """,
            expected_replacement="""
{
    'name': 'Another Module',
}
    """,
        ),
        InvalidTestCase(
            code="""
{
    "active": True,
    "installable": (
        True),
    "auto_install": (
        False),
    "name": "hello",
}
    """,
            expected_replacement="""
{
    "name": "hello",
}
    """,
        ),
    ]

    VALID = [
        ValidTestCase(
            code="""
    {
        'name': 'My Module',
        'depends': ['base'],
        'installable': False,
        'active': False,
    }
    """
        ),
        ValidTestCase(
            code="""
    {
        'name': 'My Module',
        'depends': ['base'],
    }
    """
        ),
    ]

    manifest_keys_values_true = ["active", "installable"]

    def __init__(self) -> None:
        super().__init__()
        self.name = "manifest-superfluous-key"

    def visit_DictElement(self, node: cst.DictElement) -> None:  # pylint:disable=invalid-name
        if not isinstance(node.key, cst.SimpleString):
            return
        if (
            (isinstance(node.value, cst.List) and not node.value.elements)
            or (isinstance(node.value, cst.SimpleString) and not node.value.evaluated_value)
            or (
                node.key.evaluated_value in self.manifest_keys_values_true
                and isinstance(node.value, cst.Name)
                and node.value.value == "True"
            )
            or (
                # boolean keys are `False` by default, only the ones listed in
                # `manifest_keys_values_true` are treated as `True` by default
                node.key.evaluated_value not in self.manifest_keys_values_true
                and isinstance(node.value, cst.Name)
                and node.value.value == "False"
            )
        ):
            self.report(
                node,
                "Delete empty values.",
                replacement=cst.RemoveFromParent(),
            )
