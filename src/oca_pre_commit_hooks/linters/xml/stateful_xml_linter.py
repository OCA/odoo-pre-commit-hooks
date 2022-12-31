from typing import Any, MutableMapping

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class StatefulXmlLinter(BaseXmlLinter):
    _messages = {
        **BaseXmlLinter._messages,
        **{"xml-duplicate-record-id": "Duplicate %s id in %s:%s"},
    }

    def __init__(self):
        super().__init__()
        self.xml_ids: MutableMapping[str, Any] = {}

    def on_close(self):
        super().on_close()
        self.xml_ids.clear()

    @utils.only_required_for_checks("xml-duplicate-record-id")
    def check_xml_duplicate_record_id(self, tree):
        elements = tree.xpath("//record|template")
        for elem in elements:
            elem_id = elem.get("id")
            if not elem_id:
                continue  # This is an error, as these tags MUST have an id. This is checked in the StatelessLinter.
            if elem_id in self.xml_ids:
                original_elem = self.xml_ids[elem_id]
                if original_elem.base == elem.base:
                    message_args = (original_elem.tag, "", elem.sourceline)
                else:
                    message_args = (original_elem.tag, elem.base, elem.sourceline)

                self.add_message(
                    Message("xml-duplicate-record-id", original_elem.base, message_args, original_elem.sourceline)
                )
            else:
                self.xml_ids[elem_id] = elem
