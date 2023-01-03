import re
import subprocess
import unittest

from linters.common import TEST_REPO_PATH
from linters.xml.test_xml_all_files import EXPECTED_STATEFUL_XML_MESSAGES, EXPECTED_STATELESS_XML_MESSAGES


class TestPreCommitAllFiles(unittest.TestCase):

    expected_errors = {**EXPECTED_STATEFUL_XML_MESSAGES, **EXPECTED_STATELESS_XML_MESSAGES}

    def test_all_files(self):
        with self.assertRaises(subprocess.CalledProcessError):
            result = subprocess.run(
                ["pre-commit", "try-repo", "../", "stateful-xml-checks", "stateless-xml-checks", "--all-files"],
                cwd=TEST_REPO_PATH,
                capture_output=True,
                check=True,
            )

            output = result.stdout.decode("utf-8")
            for message, count in self.expected_errors.items():
                self.assertEqual(count, len(re.findall(f"::{message}::", output)), f"failing message: {message}")
