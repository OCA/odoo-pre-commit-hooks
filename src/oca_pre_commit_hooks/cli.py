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

from oca_pre_commit_hooks import checks_odoo_module
from oca_pre_commit_hooks.global_parser import GlobalParser


def main(argv=None):
    parser = GlobalParser()
    parser.add_argument(
        "files_or_modules",
        nargs="*",
        help="Odoo __manifest__.py paths or Odoo module paths.",
    )
    if argv is None:
        argv = sys.argv[1:]
    kwargs = vars(parser.parse_args(argv))
    return checks_odoo_module.main(**kwargs)


if __name__ == "__main__":
    main()
