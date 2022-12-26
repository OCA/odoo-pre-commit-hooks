import unittest

from lxml import etree

from oca_pre_commit_hooks.linters.xml.stateless_xml_linter import StatelessXmlLinter


class TestIndependentXmlLinter(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = StatelessXmlLinter()

    def test_oe_structure_missing_id(self):
        check_name = "oe-structure-missing-id"

        self.class_ut.check_oe_structure_missing_id(etree.fromstring('<body class="oe_structure"/>'))
        self.assertTrue("body" in self.class_ut.generated_messages[check_name][0].args)

        self.class_ut.check_oe_structure_missing_id(etree.fromstring('<div class="oe_structure p-5 mt-2"/>'))
        self.assertTrue("div" in self.class_ut.generated_messages[check_name][1].args)

        self.class_ut.check_oe_structure_missing_id(etree.fromstring('<footer class="p-5 oe_structure"/>'))
        self.assertTrue("footer" in self.class_ut.generated_messages[check_name][2].args)

        self.class_ut.check_oe_structure_missing_id(
            etree.fromstring('<header class="fixed-top oe_structure sticky-xl-top"/>')
        )
        self.assertTrue("header" in self.class_ut.generated_messages[check_name][3].args)

        self.class_ut.check_oe_structure_missing_id(
            etree.fromstring('<div id="hook_website" class="oe_structure p-5 mt-2"/>')
        )
        self.assertEqual(4, len(self.class_ut.generated_messages[check_name]))

        self.class_ut.check_oe_structure_missing_id(
            etree.fromstring('<div id="editable_footer" class="oe_structure"/>')
        )
        self.assertEqual(4, len(self.class_ut.generated_messages[check_name]))
