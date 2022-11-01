import os
import re
import sys
import tempfile
import unittest
from collections import defaultdict
from contextlib import contextmanager
from itertools import chain

import oca_pre_commit_hooks

CONFIG_NAME = oca_pre_commit_hooks.global_parser.CONFIG_NAME
RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"


def assertDictEqual(self, d1, d2, msg=None):
    # pylint:disable=invalid-name
    """Original method does not show the correct item diff
    Using ordered list it is showing the diff better"""
    real_dict2list = [(i, d1[i]) for i in sorted(d1)]
    expected_dict2list = [(i, d2[i]) for i in sorted(d2)]
    self.assertEqual(real_dict2list, expected_dict2list, msg)


def get_checks_docstring(check_classes):
    checks_docstring = ""
    checks_found = set()
    for check_class in check_classes:
        check_meths = chain(
            oca_pre_commit_hooks.utils.getattr_checks(check_class, prefix="visit"),
            oca_pre_commit_hooks.utils.getattr_checks(check_class, prefix="check"),
        )
        # Sorted to avoid mutable checks order readme
        check_meths = sorted(
            list(check_meths), key=lambda m: m.__name__.replace("visit", "", 1).replace("check", "", 1).strip("_")
        )
        for check_meth in check_meths:
            if not check_meth or not check_meth.__doc__ or "* Check" not in check_meth.__doc__:
                continue
            checks_docstring += "\n" + check_meth.__doc__.strip(" \n") + "\n"
            checks_found |= set(re.findall(RE_CHECK_DOCSTRING, checks_docstring))
            checks_docstring = re.sub(r"( )+\*", "*", checks_docstring)
    return checks_found, checks_docstring


@contextmanager
def chdir(directory):
    original_dir = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(original_dir)


class ChecksCommon(unittest.TestCase):
    # pylint: disable=no-member
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.maxDiff = None

    @staticmethod
    def get_all_code_errors(all_check_errors):
        check_errors_keys = set()
        for check_errors in all_check_errors:
            check_errors_keys |= set(check_errors.keys())
        return check_errors_keys

    @staticmethod
    def get_count_code_errors(all_check_errors):
        check_errors_count = defaultdict(int)
        for check_errors in all_check_errors:
            for check, errors in check_errors.items():
                check_errors_count[check] += len(errors)
        return check_errors_count

    @staticmethod
    def re_replace(sub_start, sub_end, substitution, content):
        re_sub = re.compile(rf"^{re.escape(sub_start)}$.*^{re.escape(sub_end)}$", re.M | re.S)
        if not re_sub.findall(content):
            raise UserWarning("No matched content")
        new_content = re_sub.sub(f"{sub_start}\n\n{substitution}\n\n{sub_end}", content)
        return new_content

    def test_checks_basic(self):
        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=False)
        real_errors = self.get_count_code_errors(all_check_errors)
        # Uncommet to get sorted values to update EXPECTED_ERRORS dict
        # print("\n".join(f"'{key}':{real_errors[key]}," for key in sorted(real_errors)))
        assertDictEqual(self, real_errors, self.expected_errors)

    def test_checks_with_cli(self):
        sys.argv = ["", "--no-exit", "--no-verbose"] + self.file_paths
        all_check_errors = self.checks_cli_main()
        real_errors = self.get_count_code_errors(all_check_errors)
        assertDictEqual(self, real_errors, self.expected_errors)

    def test_checks_disable_one_by_one_with_cli(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            sys.argv = ["", "--no-exit", "--no-verbose", f"--disable={check2disable}"] + self.file_paths
            all_check_errors = self.checks_cli_main()
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, expected_errors)

    def test_checks_disable_one_by_one_with_cli_conf_file(self):
        file_tmpl = "[MESSAGES_CONTROL]\ndisable=%s"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_fname = os.path.join(tmp_dir, CONFIG_NAME)
            for check2disable in self.expected_errors:
                with open(tmp_fname, "w", encoding="UTF-8") as temp_fl:
                    content = file_tmpl % check2disable
                    temp_fl.write(content)

                expected_errors = self.expected_errors.copy()
                sys.argv = ["", "--no-exit", "--no-verbose", f"--config={temp_fl.name}"] + self.file_paths
                all_check_errors = self.checks_cli_main()
                expected_errors.pop(check2disable)
                real_errors = self.get_count_code_errors(all_check_errors)
                self.assertTrue(real_errors == expected_errors)

    def test_checks_enable_one_by_one(self):
        for check2enable in self.expected_errors:
            all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, enable={check2enable})
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, {check2enable: self.expected_errors[check2enable]})

    def test_checks_enable_one_by_one_with_cli(self):
        for check2enable in self.expected_errors:
            sys.argv = ["", "--no-exit", "--no-verbose", f"--enable={check2enable}"] + self.file_paths
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, {check2enable: self.expected_errors[check2enable]})

    def test_checks_enable_one_by_one_with_cli_conf_file(self):
        file_tmpl = "[MESSAGES_CONTROL]\nenable=%s"
        with tempfile.TemporaryDirectory() as tmp_dir:
            with chdir(tmp_dir):  # Should use the configuration file of the current path
                tmp_fname = os.path.join(tmp_dir, CONFIG_NAME)
                for check2enable in self.expected_errors:
                    with open(tmp_fname, "w", encoding="UTF-8") as temp_fl:
                        content = file_tmpl % check2enable
                        temp_fl.write(content)

                    sys.argv = ["", "--no-exit", "--no-verbose"] + self.file_paths
                    all_check_errors = self.checks_cli_main()
                    real_errors = self.get_count_code_errors(all_check_errors)
                    assertDictEqual(self, real_errors, {check2enable: self.expected_errors[check2enable]})

    def test_checks_disable_one_by_one(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, disable={check2disable})
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, expected_errors)
