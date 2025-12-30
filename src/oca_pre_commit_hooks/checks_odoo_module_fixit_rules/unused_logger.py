import libcst as cst
import libcst.matchers as m
from fixit import InvalidTestCase, ValidTestCase

from .. import checks_odoo_module_fixit_common as common


class NoUnusedLoggerInModels(common.Common):
    """Disallow unused `_logger = logging.getLogger(__name__)` in Odoo models."""

    MESSAGE = "Unused `_logger` is not allowed in Odoo models. Remove it if not used."

    VALID = [
        # Logger not defined at all
        ValidTestCase(
            """
            from odoo import models

            class Test(models.Model):
                _name = "x.test"
            """
        ),
        # Logger defined and actually used
        ValidTestCase(
            """
            import logging
            from odoo import models

            _logger = logging.getLogger(__name__)

            class Test(models.Model):
                _name = "x.test"

                def foo(self):
                    _logger.info("hello")
            """
        ),
        # Logger defined in non-models context (rule will be disabled by path)
        ValidTestCase(
            """
            import logging

            _logger = logging.getLogger(__name__)

            def helper():
                _logger.warning("ok")
            """
        ),
        # Logger different to the expected it could be to import from other places
        ValidTestCase(
            """
            import logging

            _logger = logging.getLogger('other name')

            class Test(models.Model):
                _name = "x.test"
            """
        ),
    ]

    INVALID = [
        # Logger defined but never used
        InvalidTestCase(
            code="""
            import logging
            from odoo import models

            _logger = logging.getLogger(__name__)

            class Test(models.Model):
                _name = "x.test"
            """,
            expected_replacement="""
            import logging
            from odoo import models

            class Test(models.Model):
                _name = "x.test"
            """,
        ),
        InvalidTestCase(
            code="""
            import logging
            from odoo import models

            _logger = logging.getLogger(__name__)
            """,
            expected_replacement="""
            import logging
            from odoo import models
            """,
        ),
    ]

    def __init__(self):
        super().__init__()
        self.name = "unused-logger"
        self._logger_assign: cst.Assign | None = None
        self._logger_used = False

    def visit_Assign(self, node: cst.Assign) -> None:  # noqa: B906 pylint:disable=invalid-name
        # Match: _logger = logging.getLogger(__name__)
        if m.matches(
            node,
            m.Assign(
                targets=[m.AssignTarget(target=m.Name("_logger"))],
                value=m.Call(
                    func=m.Attribute(
                        value=m.Name("logging"),
                        attr=m.Name("getLogger"),
                    ),
                    args=[
                        m.Arg(
                            value=m.Name("__name__"),
                        )
                    ],
                ),
            ),
        ):
            self._logger_assign = node

    def visit_Attribute(self, node: cst.Attribute) -> None:  # noqa: B906 pylint:disable=invalid-name
        # Match real usages like: _logger.info(...)
        if m.matches(
            node,
            m.Attribute(
                value=m.Name("_logger"),
            ),
        ):
            self._logger_used = True

    def leave_Module(self, node: cst.Module) -> None:  # noqa: B906 pylint:disable=invalid-name,unused-argument
        if self._logger_assign and not self._logger_used:
            self.report(
                self._logger_assign,
                replacement=cst.RemoveFromParent(),
            )
