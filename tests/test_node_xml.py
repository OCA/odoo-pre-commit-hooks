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


def test_xml_tag_position_autofix_preserves_template_layout():
    with temporary_module_copy("test_repo/test_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__openerp__.py")],
            enable={"xml-tag-position"},
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
            enable={"xml-tag-position", "xml-redundant-module-name"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "model_view_odoo2.xml").read_text()
        assert "<menuitem id='menu_root' name=\"Root\" />" in xml_content
        assert '<menuitem id=\'menu_root2\'\n        name="Root 2"\n        parent="menu_root"' in xml_content


def test_xml_deprecated_res_groups_category_id_autofix_preserves_format():
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-deprecated-res-groups-category-id"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "security" / "res_groups.xml").read_text()
        # Only the "category_id" of the "res.partner" record survives
        assert xml_content.count('name="category_id"') == 1
        assert '<field name="category_id" eval="[(6, 0, [])]" />' in xml_content
        assert (
            '<record id="group_see_all_approval_requests" model="res.groups">\n'
            '        <field name="name">See All Approval Requests</field>\n'
            "    </record>" in xml_content
        )
        assert (
            '<record id="group_multiline" model="res.groups">\n'
            '        <field name="name">Multiline Category</field>\n'
            "    </record>" in xml_content
        )
        assert '<record id="group_closing_tag" model="res.groups"></record>' in xml_content


def test_xml_deprecated_res_groups_category_id_not_reported_before_19():
    with temporary_module_copy("test_repo/odoo18_module") as module_dst:
        errors = checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-deprecated-res-groups-category-id"},
            no_exit=True,
            autofix=True,
        )

        assert not errors
        xml_content = (module_dst / "views" / "res_groups_category.xml").read_text()
        assert '<field name="category_id" ref="base.module_category_hidden" />' in xml_content


def test_xml_invisible_in_list_view_autofix_preserves_format():
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
            autofix=True,
        )

        xml_content = (module_dst / "views" / "invisible_in_list.xml").read_text()
        assert '<field name="state" column_invisible="True" />' in xml_content
        assert '<field name="active" column_invisible="True" />' in xml_content
        assert '<field name="type" column_invisible="True" />' in xml_content
        assert "<field name=\"email\" column_invisible='True' />" in xml_content
        assert (
            '<field\n                    name="phone"\n                    optional="show"\n'
            '                    column_invisible="True"\n                />' in xml_content
        )
        # Not autofixed: the field already has column_invisible
        assert '<field name="mobile" invisible="1" column_invisible="True" />' in xml_content
        # Valid usages are kept
        assert '<field name="state" invisible="1" />' in xml_content  # form view
        assert '<field name="phone" invisible="name == False" />' in xml_content

        errors_after = checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
        )
        assert len(errors_after) == 1
        assert errors_after[0].code == "xml-invisible-in-list-view"
        assert "field `mobile`" in errors_after[0].message

        # Idempotent: a second autofix run does not change the file
        checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
            autofix=True,
        )
        assert (module_dst / "views" / "invisible_in_list.xml").read_text() == xml_content


def test_xml_invisible_in_list_view_ignores_fields_of_nested_non_list_views():
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        xml_path = module_dst / "views" / "form_in_list.xml"
        xml_path.write_text(
            '<?xml version="1.0" encoding="UTF-8" ?>\n'
            "<odoo>\n"
            '    <record id="view_form_in_list" model="ir.ui.view">\n'
            '        <field name="name">form.in.list</field>\n'
            '        <field name="model">res.partner</field>\n'
            '        <field name="arch" type="xml">\n'
            "            <list>\n"
            '                <groupby name="partner_id">\n'
            '                    <field name="phone" invisible="1" />\n'
            "                </groupby>\n"
            '                <field name="child_ids">\n'
            "                    <form>\n"
            '                        <field name="name" invisible="1" />\n'
            "                    </form>\n"
            "                </field>\n"
            '                <field name="category_id">\n'
            "                    <kanban>\n"
            '                        <field name="color" invisible="1" />\n'
            "                    </kanban>\n"
            "                </field>\n"
            '                <field name="message_ids">\n'
            "                    <calendar>\n"
            '                        <field name="date" invisible="1" />\n'
            "                    </calendar>\n"
            "                </field>\n"
            "            </list>\n"
            "        </field>\n"
            "    </record>\n"
            "</odoo>\n"
        )
        manifest_path = module_dst / "__manifest__.py"
        manifest_path.write_text(
            manifest_path.read_text().replace("'data': [", "'data': [\n        'views/form_in_list.xml',")
        )
        before = xml_path.read_text()
        errors = checks_odoo_module.run(
            [str(manifest_path)],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
            autofix=True,
        )
        assert not [error for error in errors if error.position.filepath.endswith("form_in_list.xml")]
        assert xml_path.read_text() == before


def test_xml_invisible_in_list_view_is_skipped_before_odoo_17():
    with temporary_module_copy("test_repo/twelve_module") as module_dst:
        xml_path = module_dst / "views" / "invisible_in_list.xml"
        before = xml_path.read_text()
        errors = checks_odoo_module.run(
            [str(module_dst / "__manifest__.py")],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
            autofix=True,
        )
        assert not errors
        assert xml_path.read_text() == before


def test_xml_invisible_in_list_view_autofix_keeps_values_that_are_not_literals():
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        xml_path = module_dst / "views" / "char_reference.xml"
        xml_path.write_text(
            '<?xml version="1.0" encoding="UTF-8" ?>\n'
            "<odoo>\n"
            '    <record id="view_char_reference" model="ir.ui.view">\n'
            '        <field name="name">char.reference</field>\n'
            '        <field name="model">res.partner</field>\n'
            '        <field name="arch" type="xml">\n'
            "            <list>\n"
            '                <field name="name" invisible="&#49;" />\n'
            "            </list>\n"
            "        </field>\n"
            "    </record>\n"
            "</odoo>\n"
        )
        manifest_path = module_dst / "__manifest__.py"
        manifest_path.write_text(
            manifest_path.read_text().replace("'data': [", "'data': [\n        'views/char_reference.xml',")
        )
        before = xml_path.read_text()
        errors = checks_odoo_module.run(
            [str(manifest_path)],
            enable={"xml-invisible-in-list-view"},
            no_exit=True,
            autofix=True,
        )
        assert [error.position.filepath.endswith("char_reference.xml") for error in errors].count(True) == 1
        assert xml_path.read_text() == before
