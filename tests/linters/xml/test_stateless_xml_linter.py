import os

from linters.common import OutputCaptureTestCase, with_tmpdir
from lxml import etree

from oca_pre_commit_hooks.linters.xml.stateless_xml_linter import StatelessXmlLinter


class TestIndependentXmlLinter(OutputCaptureTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = StatelessXmlLinter()

    @with_tmpdir
    def test_invalid_xml_file(self, tmpdir):
        invalid_xml_file = os.path.join(tmpdir, "invalid_xml_file.xml")
        with open(invalid_xml_file, "w", encoding="utf-8") as xml_fd:
            xml_fd.write("""<odoo><span>Hello!!</span></odoo""")

        self.assertEqual(-1, self.class_ut.run([invalid_xml_file]))
        self.assertTrue("xml-syntax-error" in self.stdout.getvalue())
        self.assertEqual(1, self.stdout.getvalue().count(invalid_xml_file))

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

        self.class_ut.check_oe_structure_missing_id(
            etree.fromstring('<div class="oe_structure"/> <!-- oca-hooks:disable=oe-structure-missing-id -->')
        )
        self.assertEqual(4, len(self.class_ut.generated_messages[check_name]))
