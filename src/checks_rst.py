# Hooks are using print directly
# pylint: disable=print-used

import re
import sys

from restructuredtext_lint import lint_file as rst_lint


class ChecksRST:
    def __init__(self, rst_path):
        self.rst_path = rst_path

    def check_rst_syntax_error(self):
        """Check if rst file there is syntax error
        :return: (False, msg) if exists errors or (True, "") if not
        """
        errors = rst_lint(self.rst_path, encoding="UTF-8")
        for error in errors:
            msg = error.full_message
            res = re.search(
                r'No directive entry for "([\w|\-]+)"|'
                r'Unknown directive type "([\w|\-]+)"|'
                r'No role entry for "([\w|\-]+)"|'
                r'Unknown interpreted text role "([\w|\-]+)"',
                msg,
            )
            # TODO: Add support for sphinx directives after fix
            # https://github.com/twolfson/restructuredtext-lint/issues/29
            if res:
                # Skip directive errors
                continue
            msg_strip = msg.strip("\n").replace("\n", "|")
            print("%s:%d - %s" % (self.rst_path, error.line or 0, msg_strip))
        if errors:
            return False
        return True


def main_rst_syntax_error():
    global_res = True
    for fname in sys.argv[1:]:
        obj = ChecksRST(fname)
        res = obj.check_rst_syntax_error()
        if not res:
            global_res = False
    if not global_res:
        sys.exit(1)


def main():
    main_rst_syntax_error()


if __name__ == "__main__":
    main()
