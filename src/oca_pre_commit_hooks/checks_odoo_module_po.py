import os
import re
import string
import sys
from collections import defaultdict

import polib

from oca_pre_commit_hooks import utils

# Regex used from https://github.com/translate/translate/blob/9de0d72437/translate/filters/checks.py#L50-L62  # noqa
PRINTF_PATTERN = re.compile(
    r"""
        %(                          # initial %
        (?P<boost_ord>\d+)%         # boost::format style variable order, like %1%
        |
              (?:(?P<ord>\d+)\$|    # variable order, like %1$s
              \((?P<key>\w+)\))?    # Python style variables, like %(var)s
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w@]))        # type (%s, %d, etc.)
        )""",
    re.VERBOSE,
)


class StringParseError(TypeError):
    pass


class PrintfStringParseError(StringParseError):
    pass


class FormatStringParseError(StringParseError):
    pass


class ChecksOdooModulePO:
    def __init__(self, po_filename, enable, disable):
        self.enable = enable
        self.disable = disable
        self.checks_errors = defaultdict(list)
        po_filename = utils.full_norm_path(po_filename)
        top_path = utils.top_path(os.path.dirname(po_filename))
        self.po_data = {
            "filename": po_filename,
            "filename_short": os.path.relpath(po_filename, top_path),
            "data_section": os.path.basename(os.path.dirname(po_filename)),  # i18n or i18n_extra
            "top_path": top_path,
        }
        try:
            with open(po_filename, encoding="UTF-8") as filename_obj:
                # Do not use polib.pofile(self.po_data["filename"])
                # because raise the following error for PO files with syntax error:
                # pytest.PytestUnraisableExceptionWarning: Exception ignored in: <_io.FileIO [closed]>
                # Traceback (most recent call last):
                #     File "../polib.py", line 1474, in add
                #     action = getattr(self, 'handle_%s' % next_state)
                # ResourceWarning: unclosed file <_io.FileIO name='..' mode='rb' closefd=True>
                polib_entries = polib.pofile(filename_obj.read())
            self.po_data.update(
                {
                    "po": polib_entries,
                    "file_error": None,
                }
            )
        except (OSError, UnicodeDecodeError) as po_err:
            self.po_data.update(
                {
                    "po": [],
                    "file_error": po_err,
                }
            )

    @utils.only_required_for_checks("po-syntax-error")
    def check_po_syntax_error(self):
        """* Check po-syntax-error
        Check syntax of PO files from i18n* folders"""
        if not self.po_data["file_error"]:
            return
        msg = str(self.po_data["file_error"]).replace(f'{self.po_data["filename"]} ', "").strip()
        self.checks_errors["po-syntax-error"].append(f'{self.po_data["filename_short"]}:1 {msg}')

    @staticmethod
    def parse_printf(main_str, secondary_str):
        """Compute args and kwargs of main_str to parse secondary_str
        Using secondary_str%_get_printf_str_args_kwargs(main_str)
        """
        printf_args = ChecksOdooModulePO._get_printf_str_args_kwargs(main_str)
        if not printf_args:
            return
        try:
            main_str % printf_args
        except Exception:  # pylint: disable=broad-except  # pragma: no cover
            # The original source string couldn't be parsed correctly
            # So return early without error in order to avoid a false error
            return
        try:
            secondary_str % printf_args
        except Exception as exc:
            # The translated string couldn't be parsed correctly
            # with the args and kwargs of the original string
            # so it is a real error
            raise PrintfStringParseError(repr(exc)) from exc

    @staticmethod
    def parse_format(main_str, secondary_str):
        """Compute args and kwargs of main_str to parse secondary_str
        Using secondary_str.format(_get_printf_str_args_kwargs(main_str))
        """
        msgid_args, msgid_kwargs = ChecksOdooModulePO._get_format_str_args_kwargs(main_str)
        if not msgid_args and not msgid_kwargs:
            return
        try:
            main_str.format(*msgid_args, **msgid_kwargs)
        except Exception:  # pylint: disable=broad-except
            # The original source string couldn't be parsed correctly
            # So return early without error in order to avoid a false error
            return
        try:
            secondary_str.format(*msgid_args, **msgid_kwargs)
        except Exception as exc:
            # The translated string couldn't be parsed correctly
            # with the args and kwargs of the original string
            # so it is a real error
            raise FormatStringParseError(repr(exc)) from exc

    @staticmethod
    def _get_format_str_args_kwargs(format_str):
        """Get dummy args and kwargs of a format string
        e.g. format_str = '{} {} {variable}'
            dummy args = (0, 0)
            kwargs = {'variable': 0}
        return args, kwargs
        Motivation to use format_str.format(*args, **kwargs)
        and validate if it was parsed correctly
        """
        format_str_args = []
        format_str_kwargs = {}
        placeholders = []
        for line in format_str.splitlines():
            try:
                placeholders.extend(name for _, name, _, _ in string.Formatter().parse(line) if name is not None)
            except ValueError:
                continue
            for placeholder in placeholders:
                if placeholder == "":
                    # unnumbered "{} {}"
                    # append 0 to use max(0, 0, ...) == 0
                    # and identify that all args are unnumbered vs numbered
                    format_str_args.append(0)
                elif placeholder.isdigit():
                    # numbered "{0} {1} {2} {0}"
                    # append +1 to use max(1, 2) and know the quantity of args
                    # and identify that the args are numbered
                    format_str_args.append(int(placeholder) + 1)
                else:
                    # named "{var0} {var1} {var2} {var0}"
                    format_str_kwargs[placeholder] = 0
        if format_str_args:
            format_str_args = range(len(format_str_args)) if max(format_str_args) == 0 else range(max(format_str_args))
        return format_str_args, format_str_kwargs

    @staticmethod
    def _get_printf_str_args_kwargs(printf_str):
        """Get dummy args and kwargs of a printf string
        e.g. printf_str = '%s %d'
            dummy args = ('', 0)
        e.g. printf_str = '%(var1)s %(var2)d'
            dummy kwargs = {'var1': '', 'var2': 0}
        return args or kwargs
        Motivation to use printf_str % (args or kwargs)
        and validate if it was parsed correctly
        """
        args = []
        kwargs = {}

        # Remove all escaped %%
        printf_str = re.sub("%%", "", printf_str)
        for line in printf_str.splitlines():
            for match in PRINTF_PATTERN.finditer(line):
                match_items = match.groupdict()
                var = "" if match_items["type"] == "s" else 0
                if match_items["key"] is None:
                    args.append(var)
                else:
                    kwargs[match_items["key"]] = var
        return tuple(args) or kwargs

    @staticmethod
    def _get_po_line_number(po_entry):
        """Get line number of a PO entry similar to 'msgfmt' output
        entry.linenum returns line number of the definition of the entry
        'msgfmt' returns line number of the 'msgid'
        This method also gets line number of the 'msgid'
        """
        linenum = po_entry.linenum
        for line in str(po_entry).split("\n"):
            if not line.startswith("#"):
                break
            linenum += 1
        return linenum

    @utils.only_required_for_checks(
        "po-python-parse-format",
        "po-python-parse-printf",
        "po-requires-module",
    )
    def visit_entry(self, entry):
        """* Check po-requires-module
        Translation entry requires comment `#. module: MODULE`

        * Check po-python-parse-printf
        Check if `msgid` is using `str` variables like `%s`
        So translation `msgstr` must be the same number of variables too

        * Check po-python-parse-format
        Check if `msgid` is using `str` variables like `{}`
        So translation `msgstr` must be the same number of variables too
        """
        # po_requires_module
        # Regex from https://github.com/odoo/odoo/blob/fa4f36bb631e82/odoo/tools/translate.py#L616  # noqa
        match = re.match(r"(module[s]?): (\w+)", entry.comment)
        if not match:
            self.checks_errors["po-requires-module"].append(
                f'{self.po_data["filename_short"]}:{entry.linenum} '
                "Translation entry requires comment `#. module: MODULE`"
            )

        # po_msgstr_variables
        if entry.msgstr and "python-format" in entry.flags:
            # skip untranslated entry
            # skip if it is not a python format
            # because "%s"%var won't be parsed
            try:
                self.parse_printf(entry.msgid, entry.msgstr)
                self.parse_format(entry.msgid, entry.msgstr)
            except PrintfStringParseError as str_parse_exc:
                linenum = self._get_po_line_number(entry)
                self.checks_errors["po-python-parse-printf"].append(
                    f'{self.po_data["filename_short"]}:{linenum} '
                    "Translation string couldn't be parsed "
                    f"correctly using str%variables {str_parse_exc}"
                )
            except FormatStringParseError as str_parse_exc:
                linenum = self._get_po_line_number(entry)
                self.checks_errors["po-python-parse-format"].append(
                    f'{self.po_data["filename_short"]}:{linenum} '
                    "Translation string couldn't be parsed "
                    f"correctly using str.format {str_parse_exc}"
                )

    def check_po(self):
        """* Check po-duplicate-message-definition (message-id)
        in all entries of PO files

        We are not using `check_for_duplicates` parameter of polib.pofile method
            e.g. `polib.pofile(..., check_for_duplicates=True)`
        Because the output is:
            `raise ValueError('Entry "%s" already exists' % entry.msgid)`
        It doesn't show the number of lines duplicated
        and it shows the entire string of the message_id without truncating it
        or replacing newlines
        """
        duplicated = defaultdict(list)
        for entry in self.po_data["po"]:
            if entry.obsolete:
                continue

            # po_duplicate_message_definition
            duplicated[hash(entry.msgid)].append(entry)
            for meth in utils.getattr_checks(self, self.enable, self.disable, "visit_entry"):
                meth(entry)

        for entries in duplicated.values():
            if len(entries) < 2:
                continue
            linenum = self._get_po_line_number(entries[0])
            duplicated_str = ", ".join(map(str, map(self._get_po_line_number, entries[1:])))
            msg_id_short = re.sub(r"[\n\t]*", "", entries[0].msgid[:40]).strip()
            if len(entries[0].msgid) > 40:
                msg_id_short = f"{msg_id_short}..."
            self.checks_errors["po-duplicate-message-definition"].append(
                f'{self.po_data["filename_short"]}:{linenum} '
                f'Duplicate PO message definition "{msg_id_short}" '
                f"in lines {duplicated_str}"
            )

    def run_checks(self, no_verbose):
        for check in utils.getattr_checks(self, enable=self.enable, disable=self.disable):
            check()
        utils.filter_checks_enabled_disabled(self.checks_errors, self.enable, self.disable)
        for check_error, msgs in self.checks_errors.items() if not no_verbose else []:
            print(f"\n****{check_error}****")
            for msg in msgs:
                print(f"{msg} - [{check_error}]")


def run(po_files, enable=None, disable=None, no_verbose=False, no_exit=False):
    all_check_errors = []
    exit_status = 0
    for po_file in po_files:
        # Use file by file in order release memory reading file early
        checks_po_obj = ChecksOdooModulePO(po_file, enable, disable)
        try:
            checks_po_obj.run_checks(no_verbose)
            if checks_po_obj.checks_errors:
                exit_status = 1
                all_check_errors.append(checks_po_obj.checks_errors)
        finally:
            del checks_po_obj
    if no_exit:
        return all_check_errors
    sys.exit(exit_status)


def main(**kwargs):
    return run(**kwargs)
