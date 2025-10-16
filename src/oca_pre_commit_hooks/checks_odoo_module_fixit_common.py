import os

from fixit import LintRule


class Common(LintRule):
    def report(self, *args, **kwargs) -> None:
        if os.environ.get("FIXIT_AUTOFIX") != "True":
            # skip replacement to improve performance skipping the diff process
            # if autofix is not enabled
            kwargs["replacement"] = None
        return super().report(*args, **kwargs)
