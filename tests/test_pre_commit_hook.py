import os
import re
import subprocess
import sys
import unittest
from collections import Counter

from . import common, test_checks, test_checks_po

RE_CHECK_OUTPUT = r"\- \[(?P<check>[\w|-]+)\]"


def run_cmd(cmd):
    try:
        returncode = 0
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as process_error:
        returncode = process_error.returncode
        output = process_error.output
    return (returncode, output.decode(sys.stdout.encoding), " ".join(cmd))


class ChecksCommon(unittest.TestCase):
    # TODO: Create a tmp repo and run different scenarios

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.maxDiff = None
        top_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
        cls.pre_commit_hooks_yaml_path = os.path.join(top_path, ".pre-commit-hooks.yaml")
        cls.pre_commit_config_yaml_path = os.path.join(top_path, ".pre-commit-config-local.yaml")
        with open(cls.pre_commit_hooks_yaml_path, encoding="UTF-8") as f_src, open(
            cls.pre_commit_config_yaml_path, "w", encoding="UTF-8"
        ) as f_dest:
            new_content = f"""
# Do not use this file as example
# It is only to test suite
# Run "pre-commit run -c .pre-commit-config-local.yaml -v --all"
# TODO: Auto-generate from .pre-commit-hooks.yaml
repos:
  - repo: local
    hooks:
      {'      '.join(line for line in f_src)}
"""
            f_dest.write(new_content)

    def setUp(self):
        super().setUp()
        self.pre_commit_cmd = ["pre-commit", "run", "--color=never", "-avc", self.pre_commit_config_yaml_path]
        self.expected_errors = {}

    def test_checks_hook_odoo_module(self):
        self.expected_errors = test_checks.EXPECTED_ERRORS.copy()
        self.pre_commit_cmd.append("oca-checks-odoo-module")
        returncode, output, cmd_str = run_cmd(self.pre_commit_cmd)
        self.assertTrue(returncode, f"The process exited with code zero {returncode} {output}")
        checks_found = re.findall(RE_CHECK_OUTPUT, output)
        real_errors = dict(Counter(checks_found))
        common.assertDictEqual(
            self, real_errors, self.expected_errors, f"Different result than expected for\n{cmd_str}\n{output}"
        )

    def test_checks_hook_po(self):
        self.expected_errors = test_checks_po.EXPECTED_ERRORS.copy()
        self.pre_commit_cmd.append("oca-checks-po")
        returncode, output, cmd_str = run_cmd(self.pre_commit_cmd)
        self.assertTrue(returncode, f"The process exited with code zero {returncode} {output}")
        checks_found = re.findall(RE_CHECK_OUTPUT, output)
        real_errors = dict(Counter(checks_found))
        common.assertDictEqual(
            self, real_errors, self.expected_errors, f"Different result than expected for\n{cmd_str}\n{output}"
        )
