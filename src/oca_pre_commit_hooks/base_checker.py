from collections import defaultdict
from typing import Set


class BaseChecker:
    def __init__(self, enable: Set, disable: Set, module_name: str = None, autofix=False):
        self.enable = enable
        self.disable = disable
        self.autofix = autofix
        self.module_name = module_name

        self.checks_errors = defaultdict(list)
        self.needs_autofix = False
