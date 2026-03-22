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
