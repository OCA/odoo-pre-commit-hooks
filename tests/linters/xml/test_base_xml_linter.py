import unittest

from lxml import etree

from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class TestBaseXmlLinter(unittest.TestCase):
    def test_tag_is_disabled(self):
        tree = etree.fromstring(
            """
            <!-- oca-hooks:disable=nothing-being-disabled" -->
            <div class="oe_footer"/>
            """
        )
        self.assertFalse(BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//div")[0]))

        tree = etree.fromstring(
            '<!-- oca-hooks:disable=no-effect,nothing --><record id="demo_model1" model="random.model"/>'
        )
        self.assertFalse(BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//record")[0]))

        tree = etree.fromstring('<field name="hello">goodbye</field><!-- oca-hooks:disable=illogical -->')
        self.assertTrue("illogical" in BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//field")[0]))

        tree = etree.fromstring(
            '<field name="hello">goodbye</field><!-- oca-hooks:disable=illogical-msg,hello-id,last-warning -->'
        )
        self.assertEqual(
            {"illogical-msg", "hello-id", "last-warning"},
            BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//field")[0]),
        )

        tree = etree.fromstring('<body class="px-4 py-2"/><!-- Innocent comment. Not trying anything -->')
        self.assertFalse(BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//body")[0]))

        tree = etree.fromstring(
            """
            <div class="oe_header"/>
            <!-- oca-hooks:disable=nothing-being-disabled" -->
            """
        )
        self.assertFalse(BaseXmlLinter.get_tag_disabled_checks(tree.xpath("//div")[0]))

    def test_file_disabled_checks(self):
        tree = etree.fromstring(
            """
        <!-- oca-hooks:disable=xml-duplicate-record-id -->
        <odoo>
            <div/>
        </odoo>
        """
        )

        self.assertEqual({"xml-duplicate-record-id"}, BaseXmlLinter.get_file_disabled_checks(tree))

        tree = etree.fromstring(
            """
        <!-- oca-hooks:disable=xml-duplicate-record-id,oe-structure-missing-id -->
        <odoo>
            <body/>
        </odoo>
        """
        )
        self.assertEqual(
            {"xml-duplicate-record-id", "oe-structure-missing-id"}, BaseXmlLinter.get_file_disabled_checks(tree)
        )

        tree = etree.fromstring("<odoo><record/></odoo>")
        self.assertEqual(set(), BaseXmlLinter.get_file_disabled_checks(tree))

        tree = etree.fromstring(
            """
        <!-- oca-hooks : disable=xml-deprecated-data-node,
                    xml-duplicate-record-id -->
        <odoo>
            <span/>
        </odoo>
        """
        )
        self.assertEqual(
            {"xml-deprecated-data-node", "xml-duplicate-record-id"}, BaseXmlLinter.get_file_disabled_checks(tree)
        )

    def test_normalize_xml_id(self):
        self.assertEqual("web.customer_template", BaseXmlLinter.normalize_xml_id("customer_template", "web"))
        self.assertEqual("web.customer_template", BaseXmlLinter.normalize_xml_id("web.customer_template", "web"))
