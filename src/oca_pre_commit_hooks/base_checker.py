from typing import List, NamedTuple, Set, Tuple, Union

from colorama import Fore, Style


class FilePosition(NamedTuple):
    filepath: str
    line: int = 0
    column: int = 0

    def to_string(self, separator: str = ":") -> str:
        return separator.join(str(x) for x in iter(self) if x)

    def __str__(self):
        return self.to_string()


class CheckerError(NamedTuple):
    position: FilePosition
    code: str
    message: str
    info: Union[str, None] = None
    extra_positions: Union[List[FilePosition], None] = None

    def to_string(self):
        # File position with a styled separator
        res = Style.BRIGHT + Fore.RESET
        res += self.position.to_string(separator=Fore.CYAN + ":" + Style.RESET_ALL)
        res += Style.RESET_ALL
        # Extra styled separator
        res += Fore.CYAN + ":" + Style.RESET_ALL
        # Code
        res += " "
        res += Style.BRIGHT + Fore.RED + self.code + Style.RESET_ALL
        # Message
        res += " "
        res += self.message
        # Extra positions
        if self.extra_positions:
            res += "\n"
            res += Fore.YELLOW
            res += "\n".join(str(x) for x in iter(self.extra_positions))
            res += Style.RESET_ALL
        # Optional info
        if self.info:
            res += "\n"
            res += Style.DIM
            res += self.info
            res += Style.RESET_ALL
        return res

    def __str__(self):
        return self.to_string()


class BaseChecker:
    def __init__(
        self,
        enable: Set[str],
        disable: Set[str],
        module_name: Union[str, None] = None,
        module_version: Union[str, None] = None,
        autofix: bool = False,
    ):
        self.enable = enable
        self.disable = disable
        self.autofix = autofix
        self.module_name = module_name
        self.module_version = module_version

        self.checks_errors = []
        self.needs_autofix = False

    def is_message_enabled(self, message: str, extra_disable: Union[Set[str], None] = None):
        if extra_disable and message in extra_disable:
            return False
        if self.enable:
            return message in self.enable
        if self.disable:
            return message not in self.disable

        return True

    def register_error(
        self,
        code: str,
        message: str,
        filepath: str,
        line: int = 0,
        column: int = 0,
        info: Union[str, None] = None,
        extra_positions: Union[List[Tuple[str, int, int]], None] = None,
    ):
        self.checks_errors.append(
            CheckerError(
                position=FilePosition(filepath, line, column),
                code=code,
                message=message,
                info=info,
                extra_positions=[FilePosition(*x) for x in extra_positions] if extra_positions else None,
            )
        )
