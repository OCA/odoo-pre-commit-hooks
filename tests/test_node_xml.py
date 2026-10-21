import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest
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


def test_xml_deprecated_field_format_option_autofix_preserves_format():
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        xml_path = module_dst / "views" / "field_format_option.xml"
        content_before = xml_path.read_text()
        run_kwargs = {"enable": {"xml-deprecated-field-format-option"}, "no_exit": True, "autofix": True}
        checks_odoo_module.run([str(module_dst / "__manifest__.py")], **run_kwargs)

        xml_content = xml_path.read_text()
        # Only the key is renamed, the quotes, spaces and the rest of the options are kept
        changed_lines = [
            (line_before, line_after)
            for line_before, line_after in zip(content_before.splitlines(), xml_content.splitlines(), strict=True)
            if line_before != line_after
        ]
        assert len(changed_lines) == 5
        assert all(
            line_before.replace("format", "enable_formatting") == line_after
            for line_before, line_after in changed_lines
        )
        assert '<field name="year" options="{\'enable_formatting\': false}" />' in xml_content
        assert (
            '<field name="color" options=\'{"enable_formatting": False, "type": "number"}\' widget="integer" />'
            in xml_content
        )
        assert "<field name=\"sequence\" options=\"{'step': 1,  'enable_formatting' :0}\"/>" in xml_content
        assert (
            'options="{\n'
            "                        'currency_field': 'currency_id',\n"
            "                        'enable_formatting': False,\n"
            '                    }"' in xml_content
        )
        assert '<field name="debit_limit" options="{&quot;enable_formatting&quot;: true}" />' in xml_content
        # Not fixed
        assert "options=\"{'format': false, 'enable_formatting': false}\"" in xml_content
        assert "options=\"{'format': 'dd/MM/yyyy'}\"" in xml_content
        assert "options=\"{'datepicker': {'format': false}}\"" in xml_content
        assert "options=\"{'placeholder': 'format'}\"" in xml_content
        assert "t-options=\"{'widget': 'date', 'format': 'MMM d'}\"" in xml_content

        # Idempotent: a second run only reports the cases that cannot be fixed
        errors = checks_odoo_module.run([str(module_dst / "__manifest__.py")], **run_kwargs)
        assert xml_path.read_text() == xml_content
        assert len(errors) == 3


@pytest.mark.parametrize(("version", "expected_errors"), [("16.0.1.0.0", 0), ("17.0.1.0.0", 8)])
def test_xml_deprecated_field_format_option_from_17(version, expected_errors):
    with temporary_module_copy("test_repo/odoo19_module") as module_dst:
        manifest_path = module_dst / "__manifest__.py"
        manifest_path.write_text(manifest_path.read_text().replace("19.0.1.0.0", version))
        xml_path = module_dst / "views" / "field_format_option.xml"
        content_before = xml_path.read_text()
        errors = checks_odoo_module.run(
            [str(manifest_path)],
            enable={"xml-deprecated-field-format-option"},
            no_exit=True,
            autofix=True,
        )

        assert len(errors) == expected_errors
        # `enable_formatting` does not exist before 17.0, so nothing is renamed there
        assert (xml_path.read_text() == content_before) == (not expected_errors)
