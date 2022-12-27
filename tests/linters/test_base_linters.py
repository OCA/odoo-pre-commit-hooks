"""Test all methods implemented by AbstractBaseLinter."""
import os
import re
import unittest

from tests.linters.common import OutputCaptureTestCase

from oca_pre_commit_hooks.linters.abstract_base_linter import AbstractBaseLinter
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.scheduler_configuration import SchedulerConfiguration
from oca_pre_commit_hooks.utils import only_required_for_checks

test_messages = {
    "missing-dummy": "You are missing the dummy in your code",
    "no-goto": "It isn't even a thing in Python",
    "big-number": "%s is too big of a number",
}


class AbstractTestLinter(AbstractBaseLinter):
    def _check_loop(self, config: SchedulerConfiguration, file: str):
        pass

    _messages = test_messages

    @only_required_for_checks("missing-dummy")
    def check_dummy(self):
        pass

    @only_required_for_checks("no-goto")
    def check_goto(self):
        pass

    def non_check_method(self):
        pass

    @only_required_for_checks("big_number")
    def check_big_number(self):
        pass


class TestBaseLinterEnv(unittest.TestCase):
    """Tests in this class must set environment variables before instantiating the class under test, since
    argparse sets default values for arguments upon adding them."""

    def test_default_env_config_generator(self):
        enabled_msg = {"random-message-1", "xml-duplicate-record-id"}
        disabled_msg = {"xml-syntax-error", "oe-structure-missing-id"}

        os.environ[AbstractTestLinter.disable_env_var] = ",".join(disabled_msg)
        os.environ[AbstractTestLinter.enable_env_var] = ",".join(enabled_msg)

        class_ut = AbstractTestLinter()
        config = class_ut.generate_config([])
        self.assertEqual(enabled_msg, config.enable)
        self.assertEqual(disabled_msg, config.disable)

    def tearDown(self) -> None:
        os.environ.pop(AbstractTestLinter.disable_env_var)
        os.environ.pop(AbstractTestLinter.enable_env_var)


class TestBaseLinter(OutputCaptureTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.class_ut = AbstractTestLinter()

    def test_print_message_descriptions(self):
        self.class_ut.run(["--list-msgs"])

        output = self.stdout.getvalue()
        message_re = ":%s: %s\\n"
        for key, description in test_messages.items():
            self.assertTrue(bool(re.search(message_re % (key, description), output)))

    def test_get_all_checks(self):
        checks = [check.__name__ for check in self.class_ut.get_all_checks()]

        self.assertTrue("check_dummy" in checks)
        self.assertTrue("check_goto" in checks)
        self.assertTrue("check_big_number" in checks)
        self.assertFalse("non_check_method" in checks)

    def test_enable_disable_checks(self):
        checks = [check.__name__ for check in self.class_ut.get_active_checks()]
        self.assertTrue("check_dummy" in checks)
        self.assertTrue("check_goto" in checks)
        self.assertTrue("check_big_number" in checks)

        checks = [check.__name__ for check in self.class_ut.get_active_checks(enable={"missing-dummy"})]
        self.assertTrue("check_dummy" in checks)
        self.assertFalse("check_goto" in checks)
        self.assertFalse("check_big_number" in checks)

        checks = [check.__name__ for check in self.class_ut.get_active_checks(disable={"no-goto"})]
        self.assertTrue("check_dummy" in checks)
        self.assertFalse("check_goto" in checks)
        self.assertTrue("check_big_number" in checks)

        checks = [check.__name__ for check in self.class_ut.get_active_checks(enable={"missing-dummy", "no-goto"})]
        self.assertTrue("check_dummy" in checks)
        self.assertTrue("check_goto" in checks)
        self.assertFalse("check_big_number" in checks)

        checks = [check.__name__ for check in self.class_ut.get_active_checks(disable={"missing-dummy", "no-goto"})]
        self.assertFalse("check_dummy" in checks)
        self.assertFalse("check_goto" in checks)
        self.assertTrue("check_big_number" in checks)

    def test_add_and_print_message(self):
        with self.assertRaises(ValueError):
            self.class_ut.add_message(Message(key="hello", file="fake-file"))

        self.assertEqual(self.class_ut.get_exit_status(), 0)
        self.class_ut.add_message(
            Message(key="big-number", file="/tmp/my-repo/file", args=("9999",), line=20, column=1)
        )
        self.assertEqual(self.class_ut.get_exit_status(), -1)
        self.class_ut.add_message(Message(key="big-number", file="/tmp/my-repo/file", args=("5060",)))

        self.class_ut.print_generated_messages()
        self.assertFalse("/tmp/my-repo/file:-1:-1 -> 5060 is too big of a number" in self.stdout.getvalue())
        self.assertTrue("/tmp/my-repo/file:: -> 5060 is too big of a number" in self.stdout.getvalue())

    def test_zero_exit(self):
        self.class_ut.add_message(
            Message(key="big-number", file="/tmp/my-repo/file", args=("9999",), line=20, column=1)
        )
        self.assertEqual(self.class_ut.get_exit_status(), -1)
        self.assertEqual(self.class_ut.get_exit_status(True), 0)
