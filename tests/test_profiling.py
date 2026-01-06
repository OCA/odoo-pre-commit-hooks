import sys
from itertools import chain
from os import environ
from pathlib import Path

import pytest

import oca_pre_commit_hooks
from . import common
from .test_checks import EXPECTED_ERRORS as MODULES_ERRORS
from .test_checks_po import EXPECTED_ERRORS as PO_ERRORS


@pytest.mark.skipif(not environ.get("PROFILING"), reason="Profiling not enabled")
@pytest.mark.filterwarnings("ignore:GitWildMatchPattern.*:DeprecationWarning")
class TestProfiling:
    @staticmethod
    def manifests_from_repo(repo: str):
        base = Path(repo)
        return list(map(Path.as_posix, chain(base.rglob("__openerp__.py"), base.rglob("__manifest__.py"))))

    @staticmethod
    def pofiles_from_repo(repo: str):
        base = Path(repo)
        return list(map(Path.as_posix, chain(base.rglob("*.po"), base.rglob("*.pot"))))

    @classmethod
    def setup_class(cls):
        test_repo_path = (Path(__file__).resolve().parent.parent / "test_repo").as_posix()
        cls.module_files = cls.manifests_from_repo(test_repo_path)
        cls.po_files = cls.pofiles_from_repo(test_repo_path)

    def test_profile_checks_module(self, request):
        checks_module_run = oca_pre_commit_hooks.cli.main
        checks_module_run2 = oca_pre_commit_hooks.cli_fixit.main
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.module_files)
        try:
            errors = checks_module_run()
            errors += checks_module_run2()
            common.assertDictEqual(self, common.ChecksCommon.get_count_code_errors(errors), MODULES_ERRORS)
        finally:
            mp.undo()

    def test_profile_checks_po(self, request):
        checks_po_run = oca_pre_commit_hooks.cli_po.main
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + self.po_files)
        try:
            errors = checks_po_run()
            common.assertDictEqual(self, common.ChecksCommon.get_count_code_errors(errors), PO_ERRORS)
        finally:
            mp.undo()

    @pytest.mark.skipif(not environ.get("PROFILING_TEST_REPO"), reason="No custom repository set for profiling")
    def test_profile_checks_module_custom(self, request):
        manifests = self.manifests_from_repo(environ.get("PROFILING_TEST_REPO"))
        checks_module_run = oca_pre_commit_hooks.cli.main
        checks_module_run2 = oca_pre_commit_hooks.cli_fixit.main
        mp = pytest.MonkeyPatch()
        mp.setattr(sys, "argv", ["", "--no-exit", "--no-verbose"] + manifests)
        try:
            print(f"Running oca-checks-odoo-module on {len(manifests)} manifests")
            checks_module_run()
            checks_module_run2()
        finally:
            mp.undo()
