import os
import re
import subprocess
import sys
from contextlib import contextmanager
from functools import lru_cache
from itertools import chain
from pathlib import Path

CHECKS_DISABLED_REGEX = re.compile(re.escape("oca-hooks:disable=") + r"([a-z\-,]+)")
DEPRECATED_CHECKS_DISABLED_REGEX = re.compile(re.escape("pylint:disable=") + r"([a-z\-,]+)")
RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"


def checks_disabled(comment):
    comment_strip = comment.replace("\n", "").replace(" ", "").replace("#", "")
    check_disable_match = CHECKS_DISABLED_REGEX.search(comment_strip)
    check_deprecated_disable_match = DEPRECATED_CHECKS_DISABLED_REGEX.search(comment_strip)

    match = check_disable_match or check_deprecated_disable_match
    use_deprecate = bool(check_deprecated_disable_match)
    if not match:
        return [], False

    return match.groups()[0].split(","), use_deprecate


def only_required_for_checks(*checks):
    """Decorator to store checks that are handled by a checker method as an
    attribute of the function object.

    This information is used to decide whether to call the decorated
    method or not. If none of the checks is enabled, the method will be skipped.
    """

    def store_checks(func):
        setattr(func, "checks", set(checks))  # noqa: B010
        return func

    return store_checks


def only_required_for_installable():
    """Decorator to store checks that are handled by a checker method as an
    attribute of the function object.

    This information is used to decide whether to call the decorated
    method or not. If the module is not installabe, the method will be skipped.
    """

    def store_installable(func):
        setattr(func, "installable", True)  # noqa: B010
        return func

    return store_installable


def is_message_enabled(msg_code, enable, disable, disable_node=None):
    if disable_node and msg_code in disable_node:
        # If the check is disabled in the node so return early
        # because of it could be enabled for other files except this one
        return False
    if disable:
        return msg_code not in disable
    if enable:
        return msg_code in enable
    return True


def getattr_checks(obj_or_class, enable=None, disable=None, prefix="check_", disable_node=None):
    """Get all the attributes callables (methods)
    that start with word 'def check_*'
    Skip the methods with attribute "checks" defined if
    the check is not enable or if it is disabled"""
    if enable is None:
        enable = set()
    if disable is None:
        disable = set()
    if disable_node is None:
        disable_node = set()
    for attr in dir(obj_or_class):
        if not callable(getattr(obj_or_class, attr)) or not attr.startswith(prefix):
            continue
        meth = getattr(obj_or_class, attr)
        meth_checks = getattr(meth, "checks", set())
        if meth_checks and not any(
            is_message_enabled(meth_check, enable, disable, disable_node) for meth_check in meth_checks
        ):
            continue
        meth_installable = getattr(meth, "installable", None)
        is_module_installable = getattr(obj_or_class, "is_module_installable", None)
        if (
            meth_installable is not None
            and is_module_installable is not None
            and meth_installable
            and not is_module_installable
        ):
            continue
        yield getattr(obj_or_class, attr)


@contextmanager
def chdir(directory):
    """Change the current directory similar to command 'cd directory'
    but remembering the previous value to be revert at final
    Similar to run 'original_dir=$(pwd) && cd odoo && cd ${original_dir}'
    """
    original_dir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(original_dir)


@lru_cache(maxsize=256)
def top_path(path):
    """Get the top level path based on git
    If no git repository is found (and therefore no top level path), the user's HOME is returned.

    It is using lru_cache in order to re-use top level path values
    if multiple files are sharing the same path
    """
    try:
        with chdir(path):
            return (
                subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.STDOUT)
                .decode(sys.stdout.encoding)
                .strip()
            )
    except (FileNotFoundError, subprocess.CalledProcessError):
        path = Path(path)
        return path.root or Path.home()


def full_norm_path(path):
    """Expand paths in all possible ways"""
    return os.path.normpath(os.path.realpath(os.path.abspath(os.path.expanduser(os.path.expandvars(path.strip())))))


@lru_cache(maxsize=256)
def walk_up(path, filenames, top):
    """Look for "filenames" walking up in parent paths of "path"
    but limited only to "top" path
    """
    if full_norm_path(path) == full_norm_path(top):
        return None
    for filename in filenames:
        path_filename = os.path.join(path, filename)
        if os.path.isfile(full_norm_path(path_filename)):
            return path_filename
    return walk_up(os.path.dirname(path), filenames, top)


def filter_checks_enabled_disabled(checks_errors, enables, disables):
    """Remove disabled checks from "check_errors" dictionary
    It is needed since that there are checks called without option to disable them
    e.g. syntax error checks

    Remove checks not enabled only if enabled was defined
    """
    if not checks_errors:
        return
    for disable in disables or []:
        checks_errors.pop(disable, False)
    if not enables:
        return
    checks_no_enable = set(checks_errors) - enables
    for check_no_enable in checks_no_enable:
        checks_errors.pop(check_no_enable, False)


def get_checks_docstring(check_classes):
    checks_docstring = ""
    checks_found = set()
    for check_class in check_classes:
        check_meths = chain(
            getattr_checks(check_class, prefix="visit"),
            getattr_checks(check_class, prefix="check"),
        )
        # Sorted to avoid mutable checks order readme
        check_meths = sorted(
            list(check_meths), key=lambda m: m.__name__.replace("visit", "", 1).replace("check", "", 1).strip("_")
        )
        for check_meth in check_meths:
            if not check_meth or not check_meth.__doc__ or "* Check" not in check_meth.__doc__:
                continue
            checks_docstring += "\n" + check_meth.__doc__.strip(" \n") + "\n"
            checks_found |= set(re.findall(RE_CHECK_DOCSTRING, checks_docstring))
            checks_docstring = re.sub(r"( )+\*", "*", checks_docstring)
    return checks_found, checks_docstring
