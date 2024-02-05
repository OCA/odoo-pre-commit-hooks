from collections import defaultdict
from typing import Set, Union


class BaseChecker:
    def __init__(self, enable: Set, disable: Set, module_name: str = None, autofix=False):
        self.enable = enable
        self.disable = disable
        self.autofix = autofix
        self.module_name = module_name

        self.checks_errors = defaultdict(list)
        self.needs_autofix = False

    def is_message_enabled(self, message: str, extra_disable: Union[Set, None] = None):
        if extra_disable:
            return message not in extra_disable
        if self.enable:
            return message in self.enable
        if self.disable:
            return message not in self.disable

        return True
