import os
import sys


def getattr_checks(item):
    return [
        attr
        for attr in dir(item)
        if callable(getattr(item, attr)) and attr.startswith("check_")
    ]


def main(class_def, fnames, do_exit=True):
    # TODO: Choose what checks run, by default all
    success = True
    checks = getattr_checks(class_def)
    for fname in fnames:
        obj = class_def(os.path.realpath(fname))
        for check in checks:
            res = getattr(obj, check)()
            # TODO: Return file, lineno, check name and result
            if not res and success:
                success = False
    if do_exit:
        sys.exit(not success)
