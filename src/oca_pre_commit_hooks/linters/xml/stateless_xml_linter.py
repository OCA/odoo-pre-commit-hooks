from lxml import etree

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.scheduler_configuration import SchedulerConfiguration
from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class StatelessXmlLinter(BaseXmlLinter):
    _messages = {
        "xml-syntax-error": "XML file's syntax is not correct",
        "oe-structure-missing-id": "Tag <%s> has 'oe_structure' as a class and therefore must have an id",
    }

    def _check_loop(self, config: SchedulerConfiguration, file: str):
        try:
            with open(file, encoding="utf-8") as xml_fd:
                tree = etree.parse(xml_fd)
        except (etree.XMLSyntaxError, UnicodeDecodeError):
            self.add_message(Message("xml-syntax-error", file))
            return

        checks = self.get_active_checks(config.enable, config.disable)
        for check in checks:
            check(tree)

    @utils.only_required_for_checks("oe-structure-missing-id")
    def check_oe_structure_missing_id(self, tree):
        oe_structure_elements = self.find_tags_with_class(tree, "oe_structure")
        for elem in oe_structure_elements:
            if "oe-structure-missing-id" in self.get_tag_disabled_checks(elem):
                continue
            if "id" not in elem.attrib:
                self.add_message(Message("oe-structure-missing-id", elem.base, (elem.tag,), elem.sourceline))


if __name__ == "__main__":
    raise SystemExit(StatelessXmlLinter.main())
