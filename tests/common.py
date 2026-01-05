import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from distutils.dir_util import copy_tree  # pylint:disable=deprecated-module

import pytest

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.global_parser import CONFIG_NAME, DISABLE_ENV_VAR, ENABLE_ENV_VAR

RND = random.Random(987654321)


def assertDictEqual(self, d1, d2, msg=None):
    # pylint:disable=invalid-name
    """Original method does not show the correct item diff
    Using ordered list it is showing the diff better"""
    # real_dict2list = [(i, d1[i]) for i in sorted(d1)]
    # expected_dict2list = [(i, d2[i]) for i in sorted(d2)]

    diff = []
    all_keys = sorted(set(d1) | set(d2))

    for key in all_keys:
        if key not in d2:
            diff.append(f"- {key}: {d1[key]}")
        elif key not in d1:
            diff.append(f"+ {key}: {d2[key]}")
        elif d1[key] != d2[key]:
            diff.append(f"~ {key}: {d1[key]} -> {d2[key]}")

    assert not diff, f"{msg or ''}  {diff}".strip()


def create_dummy_repo(src_path, dest_path):
    copy_tree(src_path, dest_path)
    subprocess.check_call(["git", "init", dest_path, "--initial-branch=main"])
    subprocess.check_call(["git", "add", "*"], cwd=dest_path)


class ChecksCommon:
    @classmethod
    def setup_class(cls):
        cls.maxDiff = None
        cls.original_test_repo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo"
        )
        # For the inherited classes set "compatible_with_directories = True"
        # if the checks can run with directory paths
        # set False otherwise
        # e.g. "*.po" files are not compatible with directories
        cls.compatible_with_directories = True
        # os.environ.pop(ENABLE_ENV_VAR, None)
        # os.environ.pop(DISABLE_ENV_VAR, None)

    def setup_method(self, method):
        self.tmp_dir = os.path.realpath(tempfile.mkdtemp(suffix="_oca_pre_commit_hooks"))
        self.test_repo_path = self.tmp_dir
        create_dummy_repo(self.original_test_repo_path, self.tmp_dir)

    def teardown_method(self, method):
        if os.path.isdir(self.tmp_dir) and self.tmp_dir != "/":
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

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
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.file_paths)
        try:
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, self.expected_errors)
        finally:
            mp.undo()

    def _test_checks_disable_one_by_one_with_random_cli_env_conf(self, check2disable):
        """Faster way to test disable one by one using random method selection"""
        methods = [
            getattr(self, name)
            for name in dir(self)
            if name.startswith("_test_checks_disable_one_by_one")
            and callable(getattr(self, name))
            and name != "_test_checks_disable_one_by_one_with_random_cli_env_conf"
        ]
        file_paths = self.file_paths
        dir_paths = [os.path.dirname(i) for i in self.file_paths]
        method = RND.choice(methods)
        if self.compatible_with_directories:
            self.file_paths = RND.choice([file_paths, dir_paths])
        print(
            f"Method choose {method.__name__} File paths choose {'files' if dir_paths == self.file_paths else 'dirs'}"
            f" for check2disable {check2disable}"
        )
        method(check2disable)

    def _test_checks_disable_one_by_one(self, check2disable):
        expected_errors = self.expected_errors.copy()
        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, disable={check2disable})
        expected_errors.pop(check2disable)
        real_errors = self.get_count_code_errors(all_check_errors)
        assertDictEqual(self, real_errors, expected_errors, f"Disabled only {check2disable}")

    def _test_checks_disable_one_by_one_with_cli(self, check2disable):
        expected_errors = self.expected_errors.copy()
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose", f"--disable={check2disable}"] + self.file_paths)
        try:
            all_check_errors = self.checks_cli_main()
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(self, real_errors, expected_errors, f"Disabled only {check2disable}")
        finally:
            mp.undo()

    def _test_checks_disable_one_by_one_with_env(self, check2disable):
        expected_errors = self.expected_errors.copy()
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.file_paths)
        mp.setenv(DISABLE_ENV_VAR, check2disable)
        mp.delenv(ENABLE_ENV_VAR, raising=False)
        try:
            all_check_errors = self.checks_cli_main()
            expected_errors.pop(check2disable)
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self,
                real_errors,
                expected_errors,
                (
                    f"Disabled only {check2disable} environ {DISABLE_ENV_VAR}={os.getenv(DISABLE_ENV_VAR)}"
                    f" {ENABLE_ENV_VAR}={os.getenv(ENABLE_ENV_VAR)} sys.argv {sys.argv}"
                ),
            )
        finally:
            mp.undo()

    def _test_checks_disable_one_by_one_with_cli_conf_file(self, check2disable):
        file_tmpl = "[MESSAGES_CONTROL]\ndisable=%s"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_fname = os.path.join(tmp_dir, CONFIG_NAME)
            with open(tmp_fname, "w", encoding="UTF-8") as temp_fl:
                content = file_tmpl % check2disable
                temp_fl.write(content)
                temp_fl.flush()

            expected_errors = self.expected_errors.copy()
            mp = pytest.MonkeyPatch()
            mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose", f"--config={temp_fl.name}"] + self.file_paths)
            try:
                all_check_errors = self.checks_cli_main()
                expected_errors.pop(check2disable)
                real_errors = self.get_count_code_errors(all_check_errors)
                assert real_errors == expected_errors, f"Disabled only {check2disable}"
            finally:
                mp.undo()

    def _test_checks_enable_one_by_one_with_random_cli_env_conf(self, check2enable):
        """Faster way to test enable one by one using random method selection"""
        methods = [
            getattr(self, name)
            for name in dir(self)
            if name.startswith("_test_checks_enable_one_by_one")
            and callable(getattr(self, name))
            and name != "_test_checks_enable_one_by_one_with_random_cli_env_conf"
        ]
        file_paths = self.file_paths
        dir_paths = [os.path.dirname(i) for i in self.file_paths]

        method = RND.choice(methods)
        if self.compatible_with_directories:
            self.file_paths = RND.choice([file_paths, dir_paths])
        print(
            f"Method choose {method.__name__} File paths choose {'files' if dir_paths == self.file_paths else 'dirs'}"
            f" for check2disable {check2enable}"
        )
        method(check2enable)

    def _test_checks_enable_one_by_one(self, check2enable):
        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=True, enable={check2enable})
        real_errors = self.get_count_code_errors(all_check_errors)
        assertDictEqual(
            self, real_errors, {check2enable: self.expected_errors[check2enable]}, f"Enabled only {check2enable}"
        )

    def _test_checks_enable_one_by_one_with_cli(self, check2enable):
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose", f"--enable={check2enable}"] + self.file_paths)
        try:
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self, real_errors, {check2enable: self.expected_errors[check2enable]}, f"Enabled only {check2enable}"
            )
        finally:
            mp.undo()

    def _test_checks_enable_one_by_one_with_env(self, check2enable):
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.file_paths)
        mp.setenv(ENABLE_ENV_VAR, check2enable)
        mp.delenv(DISABLE_ENV_VAR, raising=False)
        try:
            all_check_errors = self.checks_cli_main()
            real_errors = self.get_count_code_errors(all_check_errors)
            assertDictEqual(
                self,
                real_errors,
                {check2enable: self.expected_errors[check2enable]},
                (
                    f"Enable only {check2enable} environ {ENABLE_ENV_VAR}={os.getenv(ENABLE_ENV_VAR)}"
                    f" {DISABLE_ENV_VAR}={os.getenv(DISABLE_ENV_VAR)} sys.argv {sys.argv}"
                ),
            )
        finally:
            mp.undo()

    def _test_checks_enable_one_by_one_with_cli_conf_file(self, check2enable):
        file_tmpl = "[MESSAGES_CONTROL]\nenable=%s"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_fname = os.path.join(tmp_dir, CONFIG_NAME)
            with open(tmp_fname, "w", encoding="UTF-8") as temp_fl:
                content = file_tmpl % check2enable
                temp_fl.write(content)
                temp_fl.flush()
            mp = pytest.MonkeyPatch()
            mp.chdir(tmp_dir)  # Should use the configuration file of the current path
            mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.file_paths)
            try:
                all_check_errors = self.checks_cli_main()
                real_errors = self.get_count_code_errors(all_check_errors)
                assertDictEqual(
                    self,
                    real_errors,
                    {check2enable: self.expected_errors[check2enable]},
                    f"Enabled only {check2enable}",
                )
            finally:
                mp.undo()

    def test_checks_enable_priority(self):
        """Verify enable configuration options have the correct priority. It should be:
        1. --enable/--disable arguments
        2. Environment variables
        3. Configuration files (either trough arguments or by being in default locations (e.g. repo root))
        """
        # TODO: Separate the test for each case
        expected_errors = list(self.expected_errors.keys())

        cli_check = expected_errors[0]
        env_check = expected_errors[1]
        conf_check = expected_errors[2]

        mp = pytest.MonkeyPatch()
        mp.setenv(ENABLE_ENV_VAR, env_check)
        mp.delenv(DISABLE_ENV_VAR, raising=False)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with open(os.path.join(tmp_dir, CONFIG_NAME), "w", encoding="UTF-8") as conf_file:
                    conf_file.write(f"[MESSAGES_CONTROL]\nenable={conf_check}")
                    conf_file.flush()

                    # First case. Only expect cli_check, it comes first over everything else
                    mp.setattr(
                        sys,
                        "argv",
                        [
                            "",
                            "--no-exit",
                            "--no-verbose",
                            f"--enable={cli_check}",
                            f"--config={conf_file.name}",
                        ]
                        + self.file_paths,
                    )
                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    assertDictEqual(self, real_errors, {cli_check: self.expected_errors[cli_check]})

                    # Second case. Only expect env_check, it overwrites whatever is in the config file
                    mp.setattr(
                        sys, "argv", ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                    )

                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    assertDictEqual(self, real_errors, {env_check: self.expected_errors[env_check]})

                    # Third case. Expect only conf_check since there is no cli argument or env var
                    mp.delenv(ENABLE_ENV_VAR, raising=False)
                    mp.delenv(DISABLE_ENV_VAR, raising=False)
                    mp.setattr(
                        sys, "argv", ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                    )
                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    assertDictEqual(self, real_errors, {conf_check: self.expected_errors[conf_check]})
        finally:
            mp.undo()

    def test_checks_disable_priority(self):
        """Verify disable configuration options have the correct priority. It should be:
        1. --enable/--disable arguments
        2. Environment variables
        3. Configuration files (either trough arguments or by being in default locations (e.g. repo root))
        """
        # TODO: Separate the test for each case
        expected_errors = list(self.expected_errors.keys())

        cli_check = expected_errors[0]
        env_check = expected_errors[1]
        conf_check = expected_errors[2]

        mp = pytest.MonkeyPatch()
        mp.setenv(DISABLE_ENV_VAR, env_check)
        mp.delenv(ENABLE_ENV_VAR, raising=False)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with open(os.path.join(tmp_dir, CONFIG_NAME), "w", encoding="UTF-8") as conf_file:
                    conf_file.write(f"[MESSAGES_CONTROL]\ndisable={conf_check}")
                    conf_file.flush()

                    # First case. Do not expect cli_check, it comes first over everything else
                    mp.setattr(
                        sys,
                        "argv",
                        [
                            "",
                            "--no-exit",
                            "--no-verbose",
                            f"--disable={cli_check}",
                            f"--config={conf_file.name}",
                        ]
                        + self.file_paths,
                    )
                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    expected_errors = self.expected_errors.copy()
                    expected_errors.pop(cli_check)
                    assertDictEqual(self, real_errors, expected_errors)

                    # Second case. Do not expect env_check, it overwrites whatever is in the config file
                    mp.setattr(
                        sys, "argv", ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                    )
                    expected_errors = self.expected_errors.copy()
                    expected_errors.pop(env_check)
                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    assertDictEqual(self, real_errors, expected_errors)

                    # Third case. Expect only conf_check since there is no cli argument or env var
                    mp.delenv(ENABLE_ENV_VAR, raising=False)
                    mp.delenv(DISABLE_ENV_VAR, raising=False)
                    mp.setattr(
                        sys, "argv", ["", "--no-exit", "--no-verbose", f"--config={conf_file.name}"] + self.file_paths
                    )
                    expected_errors = self.expected_errors.copy()
                    expected_errors.pop(conf_check)
                    real_errors = self.get_count_code_errors(self.checks_cli_main())
                    assertDictEqual(self, real_errors, expected_errors)
        finally:
            mp.undo()

    def test_list_messages(self):
        all_messages = self.checks_run([], list_msgs=True, no_exit=True, no_verbose=False)
        checks_found = re.findall(utils.RE_CHECK_DOCSTRING, all_messages)
        assert not set(self.expected_errors) - set(checks_found), "Missing list-message of checks"

    @pytest.mark.skipif(not os.getenv("DEBUG_TEST_CHECK"), reason="No message to debug was set")
    def test_debug_check(self):
        check_ut = os.getenv("DEBUG_TEST_CHECK")
        if not self.expected_errors.get(check_ut):
            return

        real_errors = self.get_count_code_errors(self.checks_run(self.file_paths, enable={check_ut}, no_exit=True))
        assertDictEqual(self, real_errors, {check_ut: self.expected_errors[check_ut]})

    def test_checks_as_string(self):
        all_check_errors = self.checks_run(self.file_paths, no_exit=True, no_verbose=False)
        for check_error in all_check_errors:
            assert str(check_error).count(check_error.code) >= 1
