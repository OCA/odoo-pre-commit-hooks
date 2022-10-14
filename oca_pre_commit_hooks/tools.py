# Hooks are using print directly
# pylint: disable=print-used

import os
import sys


def getattr_checks(item, startswith="check_"):
    for attr in dir(item):
        if not callable(getattr(item, attr)) or not attr.startswith(startswith):
            continue
        yield getattr(item, attr)


def main(obj_def, fnames, do_exit=True):
    # TODO: Choose what checks run, by default all
    success = True
    checks = getattr_checks(obj_def)
    for fname in fnames:
        obj = obj_def(os.path.realpath(fname))
        for check in checks:
            check(obj)
            for check_error, msgs in obj.checks_errors.items():
                print(f"{check_error}")
                for msg in msgs:
                    print(f"{msg}")
                success = False
    if do_exit:
        sys.exit(not success)
