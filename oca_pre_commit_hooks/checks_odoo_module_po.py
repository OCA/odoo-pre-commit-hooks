import os
from collections import defaultdict
import polib
import re

class ChecksOdooModulePO:
    def __init__(self, manifest_pos, module_name):
        self.module_name = module_name
        self.manifest_pos = manifest_pos
        self.checks_errors = defaultdict(list)
        for manifest_po in manifest_pos:
            try:
                po = polib.pofile(manifest_po["filename"])
                manifest_po.update({
                    "po": po,
                    "file_error": None,
                })
            except (IOError, OSError) as po_err:
                # TODO: Raises check_po_syntax_error
                manifest_po.update({
                    "po": None,
                    "file_error": po_err,
                })
                msg = str(po_err).replace(f'{manifest_po["filename"]} ', '').strip()
                self.checks_errors["check_po_syntax_error"].append(
                    f'{manifest_po["filename"]} {msg}'
                )

    def _get_po_line_number(self, po_entry):
        """Get line number of a PO entry similar to 'msgfmt' output
        entry.linenum returns line number of the definition of the entry
        'msgfmt' returns line number of the 'msgid'
        This method also gets line number of the 'msgid'
        """
        linenum = po_entry.linenum
        for line in str(po_entry).split('\n'):
            if not line.startswith('#'):
                break
            linenum += 1
        return linenum

    def check_po(self):
        """* Check po_requires_module
        Translation entry requires comment '#. module: MODULE'

        * Check po_duplicate_message_definition (message-id)
        in all entries of PO files

        We are not using `check_for_duplicates` parameter of polib.pofile method
            e.g. polib.pofile(..., check_for_duplicates=True)
        Because the output is:
            raise ValueError('Entry "%s" already exists' % entry.msgid)
        It doesn't show the number of lines duplicated
        and it shows the entire string of the message_id without truncating it
        or replacing newlines
        """
        for manifest_po in self.manifest_pos:
            duplicated = defaultdict(list)
            for entry in manifest_po["po"]:
                if entry.obsolete:
                    continue
                # Regex from https://github.com/odoo/odoo/blob/fa4f36bb631e82/odoo/tools/translate.py#L616  # noqa
                match = re.match(r"(module[s]?): (\w+)", entry.comment)
                if not match:
                    self.checks_errors["po_requires_module"].append(
                        f'{manifest_po["filename"]}:{entry.linenum}'
                        "Translation entry requires comment '#. module: MODULE'"
                    )
                duplicated[hash(entry.msgid)].append(entry)

            for entries in duplicated.values():
                if len(entries) < 2:
                    continue
                linenum = self._get_po_line_number(entries[0])
                duplicated_str = ', '.join(map(str, map(self._get_po_line_number, entries[1:])))
                msg_id_short = re.sub(r"[\n\t]*", "", entries[0].msgid[:40]).strip()
                if len(entries[0].msgid) > 40:
                    msg_id_short = "%s..." % msg_id_short
                self.checks_errors["po_duplicate_message_definition"].append(
                        f'{manifest_po["filename"]}:{linenum} '
                        f'Duplicate PO message definition "{msg_id_short}" in lines {duplicated_str}'
                    )
