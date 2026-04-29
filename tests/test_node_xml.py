import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from lxml import etree

from oca_pre_commit_hooks import checks_odoo_module, node_xml

REPO_ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def temporary_module_copy(module_path: str) -> Iterator[Path]:
    module_src = REPO_ROOT / module_path
    with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp_dir:
        module_dst = Path(tmp_dir) / module_src.name
        shutil.copytree(module_src, module_dst)
        yield module_dst


def test_xml_start_tag_locator_multiline_qweb_directives():
    xml_path = REPO_ROOT / "test_repo/odoo18_module/views/deprecated_qweb_directives15.xml"
    tree = etree.parse(str(xml_path))
    locator = node_xml.XMLStartTagLocator(str(xml_path), tree)

    nodes = tree.xpath("/odoo//template//*[@t-esc or @t-raw]")
    attrs = [("t-esc" if "t-esc" in node.attrib else "t-raw") for node in nodes]
    spans = [locator.get_attr(node, attr_name) for node, attr_name in zip(nodes, attrs, strict=True)]

    assert [locator.content[span.name_start : span.name_end] for span in spans] == [
        b"t-esc",
        b"t-raw",
        b"t-esc",
        b"t-esc",
    ]
    # pylint: disable=protected-access  # TODO: Check how to fix it instead of disable it
    assert [locator._element_tags[tree.getpath(node)].line for node in nodes] == [6, 7, 13, 19]


def test_xml_deprecated_qweb_directive_15_autofix_preserves_format():
    with temporary_module_copy("test_repo/odoo18_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-deprecated-qweb-directive-15"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "views" / "deprecated_qweb_directives15.xml").read_text()
        assert xml_content.count("t-esc") == 1
        assert xml_content.count("t-raw") == 1
        assert xml_content.count("t-out") == 5
        assert '<span t-out="price" />' in xml_content
        assert '<span t-out="amount" />' in xml_content
        assert '<strong>Name <t\n                    t-out="o.name"\n                />' in xml_content
        assert (
            '<p class="col"><strong>Line Template:</strong> <t\n                '
            't-out="lead.template_line_id.name"\n            /></p>' in xml_content
        )


def test_xml_id_position_first_autofix_preserves_template_layout():
    with temporary_module_copy("test_repo/test_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__openerp__.py")],
            enable={"xml-id-position-first"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "website_templates.xml").read_text()
        assert (
            '<template\n        id="assets_backend"\n        name="test_module_widget"\n        inherit_id="web.assets_backend"'
            in xml_content
        )
        assert (
            "<template\n        id='assets_backend_2'\n        name='test_module_widget_2'\n        "
            'inherit_id="web.assets_backend"\n    />' in xml_content
        )


def test_xml_record_id_autofixes_preserve_menuitem_layout():
    with temporary_module_copy("test_repo/broken_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__openerp__.py")],
            enable={"xml-id-position-first", "xml-redundant-module-name"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "model_view_odoo2.xml").read_text()
        assert "<menuitem id='menu_root' name=\"Root\" />" in xml_content
        assert '<menuitem id=\'menu_root2\'\n        name="Root 2"\n        parent="menu_root"' in xml_content


def test_xml_double_quotes_py_reports_correct_line_for_inline_and_multiline_tags():
    """Regression test: xml-double-quotes-py must report the line where the
    *attribute* is declared, not the closing line of the opening tag.

    Covers two scenarios:
    1. model_view.xml line 35: a <strong> tag with t-options spanning multiple
       lines and starting AFTER other text on the same line as <li>.
    2. website_templates.xml line 33: same pattern in a different file.
    """
    manifest_path = str(REPO_ROOT / "test_repo/test_module/__openerp__.py")
    result = checks_odoo_module.run(
        [manifest_path],
        enable={"xml-double-quotes-py"},
        no_exit=True,
    )
    errors = [e for e in result if getattr(e, "code", None) == "xml-double-quotes-py"]

    # model_view.xml: <strong t-out="o.coverage*100" t-options="{&quot;...&quot;}">
    # The tag <strong starts after <li>text on line 33, t-options is on line 35
    model_view_lines = {e.position.line for e in errors if "model_view.xml" in e.position.filepath}
    assert 35 in model_view_lines, (
        f"Expected xml-double-quotes-py error on model_view.xml:35 (t-options with &quot;), "
        f"got lines: {sorted(model_view_lines)}"
    )

    # website_templates.xml: <strong t-options on line 33
    tmpl_lines = {e.position.line for e in errors if "website_templates.xml" in e.position.filepath}
    assert 33 in tmpl_lines, (
        f"Expected xml-double-quotes-py error on website_templates.xml:33 (t-options with &quot;), "
        f"got lines: {sorted(tmpl_lines)}"
    )
