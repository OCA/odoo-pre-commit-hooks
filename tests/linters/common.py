import os
import sys
import tempfile
import unittest
from functools import wraps
from io import StringIO
from os.path import join, pardir, realpath

TEST_REPO_PATH: str = realpath(join(realpath(__file__), pardir, pardir, pardir, "test_repo"))


class OutputCaptureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        # Redirect stdout to a buffer for reading
        self.stdout = StringIO()
        self.old_stdout = sys.stdout
        sys.stdout = self.stdout

    def tearDown(self) -> None:
        super().tearDown()
        sys.stdout = self.old_stdout


def with_tmpdir(func):
    @wraps(func)
    def decorator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            func(self, tmpdir)

    return decorator


def with_chdir(path: str):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            original_dir = os.getcwd()
            try:
                os.chdir(path)
                func(self)
            finally:
                os.chdir(original_dir)

        return wrapper

    return decorator
