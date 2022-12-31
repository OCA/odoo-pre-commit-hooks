import unittest

from lxml import etree

from oca_pre_commit_hooks.linters.xml.stateful_xml_linter import StatefulXmlLinter


class TestStatefulXmlLinter(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = StatefulXmlLinter()

    def test_xml_duplicate_record_id(self):
        check_name = "xml-duplicate-record-id"

        etree_1 = etree.fromstring(
            """
        <odoo>
            <record id="task_1" model="project.task"/>
            <record id="task_2" model="project.task"/>
            <record id="task_3" model="project.task"/>
        </odoo>
        """
        )
        etree_1.base = "etree_1"
        etree_2 = etree.fromstring(
            """
        <odoo>
            <record id="task_1" model="project.task"/>
            <record id="task_4" model="project.task"/>
            <record id="task_3" model="project.task"/>
        </odoo>
        """
        )
        etree_2.base = "etree_2"

        self.class_ut.on_open()
        self.class_ut.check_xml_duplicate_record_id(etree_1)
        self.class_ut.check_xml_duplicate_record_id(etree_2)
        self.class_ut.on_close()

        self.assertEqual(2, len(self.class_ut.generated_messages[check_name]))

        self.class_ut.generated_messages.clear()
        etree_1 = etree.fromstring(
            """
        <odoo>
            <template id="website_header"/>
            <template id="website_footer"/>
            <template id="website_header"/>
            <record model="sale.order"/>
        </odoo>
        """
        )
        etree_1.base = "etree_1"
        etree_2 = etree.fromstring(
            """
        <odoo>
            <template id="website_footer"/>
        </odoo>
        """
        )
        etree_2.base = "etree_2"

        self.class_ut.on_open()
        self.class_ut.check_xml_duplicate_record_id(etree_1)
        self.class_ut.check_xml_duplicate_record_id(etree_2)
        self.class_ut.on_close()

        self.assertEqual(2, len(self.class_ut.generated_messages[check_name]))
