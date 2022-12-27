from os.path import join

from lxml import etree

from tests.linters.common import OutputCaptureTestCase, with_tmpdir

from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class TestBaseXmlLinter(OutputCaptureTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = BaseXmlLinter()

    @with_tmpdir
    def test_invalid_xml_file(self, tmpdir):
        invalid_xml_file = join(tmpdir, "invalid_xml_file.xml")
        with open(invalid_xml_file, "w", encoding="utf-8") as xml_fd:
            xml_fd.write("""<odoo><span>Hello!!</span></odoo""")

        self.assertEqual(-1, self.class_ut.run([invalid_xml_file]))
        self.assertTrue("xml-syntax-error" in self.stdout.getvalue())
        self.assertEqual(1, self.stdout.getvalue().count(invalid_xml_file))

    def test_tag_is_disabled(self):
        tree = etree.fromstring(
            """
            <!-- oca-hooks:disable=nothing-being-disabled" -->
            <div class="oe_footer"/>
            """
        )
        self.assertFalse(self.class_ut.get_tag_disabled_checks(tree.xpath("//div")[0]))

        tree = etree.fromstring(
            '<!-- oca-hooks:disable=no-effect,nothing --><record id="demo_model1" model="random.model"/>'
        )
        self.assertFalse(self.class_ut.get_tag_disabled_checks(tree.xpath("//record")[0]))

        tree = etree.fromstring('<field name="hello">goodbye</field><!-- oca-hooks:disable=illogical -->')
        self.assertTrue("illogical" in self.class_ut.get_tag_disabled_checks(tree.xpath("//field")[0]))

        tree = etree.fromstring(
            '<field name="hello">goodbye</field><!-- oca-hooks:disable=illogical-msg,hello-id,last-warning -->'
        )
        self.assertEqual(
            ["illogical-msg", "hello-id", "last-warning"],
            self.class_ut.get_tag_disabled_checks(tree.xpath("//field")[0]),
        )

        tree = etree.fromstring('<body class="px-4 py-2"/><!-- Innocent comment. Not trying anything -->')
        self.assertFalse(self.class_ut.get_tag_disabled_checks(tree.xpath("//body")[0]))

        tree = etree.fromstring(
            """
            <div class="oe_header"/>
            <!-- oca-hooks:disable=nothing-being-disabled" -->
            """
        )
        self.assertFalse(self.class_ut.get_tag_disabled_checks(tree.xpath("//div")[0]))
