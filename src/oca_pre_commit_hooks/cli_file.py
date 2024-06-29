#!/usr/bin/env python3
"""Module that contains the command line app.
Why does this file exist, and why not put this in __main__?
  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:
  - When you run `python -mpre_commit_vauxoo` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``pre_commit_vauxoo.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``pre_commit_vauxoo.__main__`` in ``sys.modules``.
  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""

import sys

from oca_pre_commit_hooks import checks_odoo_files
from oca_pre_commit_hooks.global_parser import GlobalParser


def main(argv=None):
    parser = GlobalParser()
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths which contain data files.",
    )
    parser.add_argument(
        "--autofix-char",
        help="Character to use to fill spaces in file names (default: _)",
        metavar="CHAR"
    )
    if argv is None:
        argv = sys.argv[1:]
    kwargs = vars(parser.parse_args(argv))
    return checks_odoo_files.main(**kwargs)


if __name__ == "__main__":
    main()
