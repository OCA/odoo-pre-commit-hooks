import sys
import tempfile
import unittest
from functools import wraps
from io import StringIO


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
