import sys
from contextlib import contextmanager
from cProfile import Profile
from glob import glob
from os import environ
from os.path import dirname, join, realpath
from pstats import Stats
from sys import stdout

import pytest

import oca_pre_commit_hooks
from . import common
from .test_checks import EXPECTED_ERRORS as MODULES_ERRORS
from .test_checks_po import EXPECTED_ERRORS as PO_ERRORS


@contextmanager
def cprofile():
    profiler = Profile()

    profiler.enable()
    yield
    profiler.disable()

    stats = Stats(profiler, stream=stdout)
    stats.strip_dirs()
    stats.sort_stats("cumtime")
    stats.print_stats()


@pytest.mark.skipif(not environ.get("PROFILING"), reason="Profiling not enabled")
class TestProfiling:
    @staticmethod
    def manifests_from_repo(repo: str):
        return glob(join(repo, "**", "__openerp__.py"), recursive=True) + glob(
            join(repo, "**", "__manifest__.py"), recursive=True
        )

    @staticmethod
    def pofiles_from_repo(repo: str):
        po_glob_pattern = join(repo, "**", "*.po")
        pot_glob_pattern = f"{po_glob_pattern}t"

        return glob(po_glob_pattern, recursive=True) + glob(pot_glob_pattern, recursive=True)

    @classmethod
    def setup_class(cls):
        test_repo_path = join(dirname(dirname(realpath(__file__))), "test_repo")

        cls.module_files = cls.manifests_from_repo(test_repo_path)
        cls.po_files = cls.pofiles_from_repo(test_repo_path)

    def test_profile_checks_module(self):
        checks_module_run = oca_pre_commit_hooks.cli.main
        checks_module_run2 = oca_pre_commit_hooks.cli_fixit.main

        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.module_files)
        try:
            with cprofile():
                errors = checks_module_run()
                errors += checks_module_run2()
            common.assertDictEqual(self, common.ChecksCommon.get_count_code_errors(errors), MODULES_ERRORS)
        finally:
            mp.undo()

    def test_profile_checks_po(self):
        checks_po_run = oca_pre_commit_hooks.cli_po.main
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.po_files)
        try:
            with cprofile():
                errors = checks_po_run()
            common.assertDictEqual(self, common.ChecksCommon.get_count_code_errors(errors), PO_ERRORS)
        finally:
            mp.undo()

    @pytest.mark.skipif(not environ.get("PROFILING_TEST_REPO"), reason="No custom repository set for profiling")
    def test_profile_checks_module_custom(self):
        manifests = self.manifests_from_repo(environ.get("PROFILING_TEST_REPO"))
        checks_module_run = oca_pre_commit_hooks.cli.main
        checks_module_run2 = oca_pre_commit_hooks.cli_fixit.main
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + manifests)
        try:
            print(f"Running oca-checks-odoo-module on {len(manifests)} manifests")
            with cprofile():
                checks_module_run()
                checks_module_run2()
        finally:
            mp.undo()
