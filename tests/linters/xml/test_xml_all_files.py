import glob
import os

from linters.common import TEST_REPO_PATH, OutputCaptureTestCase, with_chdir

from oca_pre_commit_hooks.linters.xml.stateful_xml_linter import StatefulXmlLinter
from oca_pre_commit_hooks.linters.xml.stateless_xml_linter import StatelessXmlLinter

EXPECTED_STATEFUL_XML_MESSAGES = {"xml-duplicate-record-id": 2}
EXPECTED_STATELESS_XML_MESSAGES = {"xml-syntax-error": 3, "oe-structure-missing-id": 1}


class TestXmlAllFiles(OutputCaptureTestCase):
    @classmethod
    @with_chdir(TEST_REPO_PATH)
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.xml_files = [os.path.relpath(xml) for xml in glob.glob(os.path.join("**/", "*.xml"), recursive=True)]

    @with_chdir(TEST_REPO_PATH)
    def test_all_xml_stateful(self):
        class_ut = StatefulXmlLinter()

        self.assertEqual(-1, class_ut.run(self.xml_files))
        self.assertEqual(2, len(class_ut.generated_messages["xml-duplicate-record-id"]))

    @with_chdir(TEST_REPO_PATH)
    def test_all_xml_stateless(self):
        class_ut = StatelessXmlLinter()

        self.assertEqual(-1, class_ut.run(self.xml_files))
