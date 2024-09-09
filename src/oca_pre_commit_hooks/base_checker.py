from typing import Set, Union

from colorama import Fore, Style


class CheckerError:
    def __init__(
        self,
        code: str,
        message: str,
        filepath: str,
        line: Union[int, None] = None,
        column: Union[int, None] = None,
        info: Union[str, None] = None,
    ):
        self.code = code
        self.message = message
        self.filepath = filepath
        self.line = line
        self.column = column
        self.info = info

    def to_string(self):
        res = Style.BRIGHT + Fore.RESET + self.filepath + Style.RESET_ALL
        if self.line is not None:
            res += Fore.CYAN + ":" + Style.RESET_ALL + str(self.line)
        if self.column is not None:  # pragma: no cover
            res += Fore.CYAN + ":" + Style.RESET_ALL + str(self.column)
        if not self.code and not self.message:  # pragma: no cover
            return res
        res += Fore.CYAN + ":" + Style.RESET_ALL
        if self.code:
            res += " "
            res += Style.BRIGHT + Fore.RED + self.code + Style.RESET_ALL
        if self.message:
            res += " "
            res += self.message
        return res

    def __str__(self):
        return self.to_string()


class BaseChecker:
    def __init__(
        self,
        enable: Set[str],
        disable: Set[str],
        module_name: Union[str, None] = None,
        autofix: bool = False,
    ):
        self.enable = enable
        self.disable = disable
        self.autofix = autofix
        self.module_name = module_name

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
        line: Union[int, None] = None,
        column: Union[int, None] = None,
        info: Union[str, None] = None,
    ):
        self.checks_errors.append(
            CheckerError(
                code=code,
                message=message,
                filepath=filepath,
                line=line,
                column=column,
                info=info,
            )
        )
