import os
import unittest

from linters.common import TEST_REPO_PATH, with_chdir
from lxml import etree

from oca_pre_commit_hooks.linters.xml.stateful_xml_linter import StatefulXmlLinter


class TestStatefulXmlLinter(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = StatefulXmlLinter()

    @with_chdir(TEST_REPO_PATH)
    def test_xml_files_from_manifest(self):
        test_module_root = "test_module"
        test_module_manifest = os.path.join(test_module_root, "__openerp__.py")
        expected_xml_files = [
            os.path.join(test_module_root, file)
            for file in [
                "res_users.xml",
                "model_view.xml",
                "website_templates.xml",
                "website_templates_disable.xml",
            ]
        ]

        self.assertCountEqual(expected_xml_files, self.class_ut.xml_files_from_manifest(test_module_manifest)["data"])

    @with_chdir(TEST_REPO_PATH)
    def test_manifest_from_xml(self):
        broken_module2_manifest = os.path.join("broken_module2", "__openerp__.py")
        broken_module2_xml = os.path.join("broken_module2", "tests", "data", "odoo_data_noupdate_1.xml")
        self.assertEqual(broken_module2_manifest, self.class_ut.manifest_from_file(broken_module2_xml))

        womanifest_module = os.path.join("womanifest_module", "__init__.py")
        self.assertEqual("", self.class_ut.manifest_from_file(womanifest_module))

        broken_module_manifest = os.path.join("broken_module", "__openerp__.py")
        broken_module_demo = os.path.join("broken_module", "demo/duplicated_id_demo.xml")
        broken_module_report = os.path.join("broken_module", "report.xml")

        self.assertEqual(broken_module_manifest, self.class_ut.manifest_from_file(broken_module_demo))
        self.assertEqual(broken_module_manifest, self.class_ut.manifest_from_file(broken_module_report))

        test_module_manifest = os.path.join("test_module", "__openerp__.py")
        test_module_xml = os.path.join("test_module", "static", "src", "xml", "widget.xml")

        self.assertEqual(test_module_manifest, self.class_ut.manifest_from_file(test_module_xml))

    def test_xml_duplicate_record_id(self):
        def tree_with_base(content: str, base: str = "test_file"):
            tree = etree.fromstring(content)
            tree.base = base
            return tree

        check_name = "xml-duplicate-record-id"
        module_name = "sale"

        # Find duplicate ids in the same file
        xml_tree = tree_with_base(
            """
        <odoo>
        <record id="duplicate_id" model="sale.order"/>
        <record id="non_duplicate_id" model="sale.order"/>
        <record id="duplicate_id" model="sale.order"/>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.on_close()
        self.assertEqual(1, len(self.class_ut.generated_messages[check_name]))
        self.class_ut.generated_messages.clear()

        # Find duplicate ids when one uses the module's name and the other does not (they eval to the same id)
        xml_tree = tree_with_base(
            """
        <odoo>
        <record id="duplicate_id" model="sale.order"/>
        <record id="sale.duplicate_id" model="sale.order"/>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.on_close()
        self.assertEqual(1, len(self.class_ut.generated_messages[check_name]))
        self.class_ut.generated_messages.clear()

        # Not duplicate since they belong to different modules
        xml_tree = tree_with_base(
            """
        <odoo>
        <record id="duplicate_id" model="sale.order"/>
        <record id="project.duplicate_id" model="sale.order"/>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.on_close()
        self.assertFalse(self.class_ut.generated_messages)
        self.class_ut.generated_messages.clear()

        # Not duplicate because they belong to <data> tags with different attributes:
        xml_tree = tree_with_base(
            """
        <odoo>
        <data>
            <record id="duplicate_id"/>
        </data>
        <data noupdate="1">
            <record id="duplicate_id"/>
        </data>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.on_close()
        self.assertFalse(self.class_ut.generated_messages)
        self.class_ut.generated_messages.clear()

        # Duplicate because even though they are different parents, they both have the same attributes
        xml_tree = tree_with_base(
            """
        <odoo>
        <data>
            <record id="duplicate_id"/>
        </data>
        <data>
            <record id="duplicate_id"/>
        </data>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.on_close()
        self.assertEqual(1, len(self.class_ut.generated_messages[check_name]))
        self.class_ut.generated_messages.clear()

        # Not duplicate since one record is declared in the data folder while the other one in demo
        xml_tree = tree_with_base(
            """
        <odoo>
        <record id="duplicate_id"/>
        </odoo>
        """
        )
        demo_xml_tree = tree_with_base(
            """
        <odoo>
        <record id="duplicate_id"/>
        </odoo>
        """
        )
        self.class_ut.check_xml_duplicate_record_id(xml_tree, module_name, "data")
        self.class_ut.check_xml_duplicate_record_id(demo_xml_tree, module_name, "demo")
        self.class_ut.on_close()
        self.assertFalse(self.class_ut.generated_messages)
