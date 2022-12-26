from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class StatelessXmlLinter(BaseXmlLinter):
    _messages = {
        **BaseXmlLinter._messages,
        **{"oe-structure-missing-id": "Tag <%s> has 'oe_structure' as a class and therefore must have an id"},
    }

    @utils.only_required_for_checks("oe-structure-missing-id")
    def check_oe_structure_missing_id(self, tree):
        oe_structure_elements = self.find_tags_with_class(tree, "oe_structure")
        for elem in oe_structure_elements:
            if "id" not in elem.attrib:
                self.add_message(Message("oe-structure-missing-id", elem.base, (elem.tag,), elem.sourceline))
