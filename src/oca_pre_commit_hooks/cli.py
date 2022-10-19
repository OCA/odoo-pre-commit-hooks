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

import argparse
import sys

from oca_pre_commit_hooks import checks_odoo_module, checks_odoo_module_po


def parse_disable(value):
    return set(value.split(","))


def global_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-verbose",
        action="store_true",
        default=False,
        help="If enabled so disable verbose mode.",
    )
    parser.add_argument(
        "--no-exit",
        action="store_true",
        default=False,
        help="If enabled so it will not call exit.",
    )
    parser.add_argument(
        "--disable",
        "-d",
        type=parse_disable,
        default=set(),
        help="Disable the checker with the given 'check-name', separated by commas.",
    )
    parser.add_argument(
        "--enable",
        "-e",
        type=parse_disable,
        default=set(),
        help=(
            "Enable the checker with the given 'check-name', separated by commas. "
            "Default: All checks are enabled by default"
        ),
    )
    # TODO: Add argument to show current checks
    return parser


def main(argv=None):
    parser = global_parser()
    parser.add_argument(
        "files_or_modules",
        nargs="*",
        help="Odoo __manifest__.py paths or Odoo module paths.",
    )
    if argv is None:
        argv = sys.argv[1:]
    kwargs = vars(parser.parse_args(argv))
    return checks_odoo_module.main(**kwargs)


def main_po(argv=None):
    parser = global_parser()
    parser.add_argument(
        "po_files",
        nargs="*",
        help="PO files.",
    )
    if argv is None:
        argv = sys.argv[1:]
    kwargs = vars(parser.parse_args(argv))
    return checks_odoo_module_po.main(**kwargs)
