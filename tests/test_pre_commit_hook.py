import os
import re
import subprocess
import sys

from . import common, test_checks, test_checks_po


def run_cmd(cmd):
    try:
        returncode = 0
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as process_error:
        returncode = process_error.returncode
        output = process_error.output
    return (returncode, output.decode(sys.stdout.encoding), " ".join(cmd))


class ChecksCommon:
    # TODO: Create a tmp repo and run different scenarios

    @classmethod
    def setup_class(cls):
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

    def setup_method(self, method):
        self.pre_commit_cmd = ["pre-commit", "run", "--color=never", "-avc", self.pre_commit_config_yaml_path]
        self.expected_errors = {}

    def test_checks_hook_odoo_module(self):
        self.expected_errors = test_checks.EXPECTED_ERRORS.copy()
        returncode, output, cmd_str = run_cmd(self.pre_commit_cmd + ["oca-checks-odoo-module"])
        _returncode2, output2, _cmd_str2 = run_cmd(self.pre_commit_cmd + ["oca-checks-odoo-module-fixit"])
        # TODO: Check output2 is returning color if it is using color=never
        ansi = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
        output2 = ansi.sub("", output2)
        output += output2
        assert returncode, f"The process exited with code zero {returncode} {output}"
        errors_count = {code: output.count(f": {code.replace('`', '')} ") for code in self.expected_errors}
        common.assertDictEqual(
            self, errors_count, self.expected_errors, f"Different result than expected for\n{cmd_str}\n{output}"
        )

    def test_checks_hook_po(self):
        self.expected_errors = test_checks_po.EXPECTED_ERRORS.copy()
        self.pre_commit_cmd.append("oca-checks-po")
        returncode, output, cmd_str = run_cmd(self.pre_commit_cmd)
        assert returncode, f"The process exited with code zero {returncode} {output}"
        errors_count = {code: output.count(code) for code in self.expected_errors}
        common.assertDictEqual(
            self, errors_count, self.expected_errors, f"Different result than expected for\n{cmd_str}\n{output}"
        )
