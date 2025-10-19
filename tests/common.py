import os
import re
import sys
import tempfile
import unittest
from collections import defaultdict
from contextlib import contextmanager

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.global_parser import CONFIG_NAME, DISABLE_ENV_VAR, ENABLE_ENV_VAR


def assertDictEqual(self, d1, d2, msg=None):
    # pylint:disable=invalid-name
    """Original method does not show the correct item diff
    Using ordered list it is showing the diff better"""
    real_dict2list = [(i, d1[i]) for i in sorted(d1)]
    expected_dict2list = [(i, d2[i]) for i in sorted(d2)]
    self.assertEqual(real_dict2list, expected_dict2list, msg)


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

    def setUp(self):
        super().setUp()
        os.environ.pop(DISABLE_ENV_VAR, None)
        os.environ.pop(ENABLE_ENV_VAR, None)

    @staticmethod
    def get_grouped_errors(all_check_errors):
        grouped_errors = defaultdict(list)
        for check_error in all_check_errors:
            grouped_errors[check_error.code].append(check_error)
        return grouped_errors

    @staticmethod
    def get_count_code_errors(all_check_errors):
        grouped_errors = ChecksCommon.get_grouped_errors(all_check_errors)
        return {code: len(errors) for code, errors in grouped_errors.items()}

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
            assertDictEqual(self, real_errors, expected_errors, f"Disabled only {check2disable}")

    def test_checks_disable_one_by_one_with_env(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            sys.argv = ["", "--no-exit", "--no-verbose"] + self.file_paths
            os.environ[DISABLE_ENV_VAR] = check2disable
            all_check_errors = self.checks_cli_main()
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, expected_errors, f"Disabled only {check2disable}")

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
                self.assertTrue(real_errors == expected_errors, f"Disabled only {check2disable}")

    def test_checks_enable_one_by_one(self):
        for check2enable in self.expected_errors:
            all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, enable={check2enable})
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self, real_errors, {check2enable: self.expected_errors[check2enable]}, f"Enabled only {check2enable}"
            )

    def test_checks_enable_one_by_one_with_cli(self):
        for check2enable in self.expected_errors:
            sys.argv = ["", "--no-exit", "--no-verbose", f"--enable={check2enable}"] + self.file_paths
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self, real_errors, {check2enable: self.expected_errors[check2enable]}, f"Enabled only {check2enable}"
            )

    def test_checks_enable_one_by_one_with_env(self):
        for check2enable in self.expected_errors:
            sys.argv = ["", "--no-exit", "--no-verbose"] + self.file_paths
            os.environ[ENABLE_ENV_VAR] = check2enable
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self, real_errors, {check2enable: self.expected_errors[check2enable]}, f"Enabled only {check2enable}"
            )

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
                    assertDictEqual(
                        self,
                        real_errors,
                        {check2enable: self.expected_errors[check2enable]},
                        f"Enabled only {check2enable}",
                    )

    def test_checks_disable_one_by_one(self):
        for check2disable in self.expected_errors:
            expected_errors = self.expected_errors.copy()
            all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, disable={check2disable})
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, expected_errors, f"Disabled only {check2disable}")

    def test_checks_enable_priority(self):
        """Verify enable configuration options have the correct priority. It should be:
        1. --enable/--disable arguments
        2. Environment variables
        3. Configuration files (either trough arguments or by being in default locations (e.g. repo root))
        """
        expected_errors = list(self.expected_errors.keys())

        cli_check = expected_errors[0]
        env_check = expected_errors[1]
        conf_check = expected_errors[2]

        os.environ[ENABLE_ENV_VAR] = env_check
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, CONFIG_NAME), "w", encoding="UTF-8") as conf_file:
                conf_file.write(f"[MESSAGES_CONTROL]\nenable={conf_check}")
                conf_file.flush()

                # First case. Only expect cli_check, it comes first over everything else
                sys.argv = [
                    "",
                    "--no-exit",
                    "--no-verbose",
                    f"--enable={cli_check}",
                    f"--config={conf_file.name}",
                ] + self.file_paths
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                assertDictEqual(self, real_errors, {cli_check: self.expected_errors[cli_check]})

                # Second case. Only expect env_check, it overwrites whatever is in the config file
                sys.argv = ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                assertDictEqual(self, real_errors, {env_check: self.expected_errors[env_check]})

                # Third case. Expect only conf_check since there is no cli argument or env var
                os.environ.pop(ENABLE_ENV_VAR, None)
                sys.argv = ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                assertDictEqual(self, real_errors, {conf_check: self.expected_errors[conf_check]})

    def test_checks_disable_priority(self):
        """Verify disable configuration options have the correct priority. It should be:
        1. --enable/--disable arguments
        2. Environment variables
        3. Configuration files (either trough arguments or by being in default locations (e.g. repo root))
        """
        expected_errors = list(self.expected_errors.keys())

        cli_check = expected_errors[0]
        env_check = expected_errors[1]
        conf_check = expected_errors[2]

        os.environ[DISABLE_ENV_VAR] = env_check
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, CONFIG_NAME), "w", encoding="UTF-8") as conf_file:
                conf_file.write(f"[MESSAGES_CONTROL]\ndisable={conf_check}")
                conf_file.flush()

                # First case. Do not expect cli_check, it comes first over everything else
                sys.argv = [
                    "",
                    "--no-exit",
                    "--no-verbose",
                    f"--disable={cli_check}",
                    f"--config={conf_file.name}",
                ] + self.file_paths
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                expected_errors = self.expected_errors.copy()
                expected_errors.pop(cli_check)
                assertDictEqual(self, real_errors, expected_errors)

                # Second case. Do not expect env_check, it overwrites whatever is in the config file
                sys.argv = ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                expected_errors = self.expected_errors.copy()
                expected_errors.pop(env_check)
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                assertDictEqual(self, real_errors, expected_errors)

                # Third case. Expect only conf_check since there is no cli argument or env var
                os.environ.pop(DISABLE_ENV_VAR, None)
                sys.argv = ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                expected_errors = self.expected_errors.copy()
                expected_errors.pop(conf_check)
                real_errors = self.get_count_code_errors(self.checks_cli_main())
                assertDictEqual(self, real_errors, expected_errors)

    def test_list_messages(self):
        all_messages = self.checks_run([], list_msgs=True, no_exit=True, no_verbose=False)
        checks_found = re.findall(utils.RE_CHECK_DOCSTRING, all_messages)
        self.assertFalse(set(self.expected_errors) - set(checks_found), "Missing list-message of checks")

    @unittest.skipUnless(os.getenv("DEBUG_TEST_CHECK"), "No message to debug was set")
    def test_debug_check(self):
        check_ut = os.getenv("DEBUG_TEST_CHECK")
        if not self.expected_errors.get(check_ut):
            return

        real_errors = self.get_count_code_errors(self.checks_run(self.file_paths, enable={check_ut}, no_exit=True))
        assertDictEqual(self, real_errors, {check_ut: self.expected_errors[check_ut]})

    def test_checks_as_string(self):
        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=False)
        for check_error in all_check_errors:
            self.assertTrue(str(check_error).count(check_error.code) >= 1)
