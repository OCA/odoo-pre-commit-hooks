from lxml import etree

from oca_pre_commit_hooks.linters.abstract_base_linter import AbstractBaseLinter
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.scheduler_configuration import SchedulerConfiguration


class BaseXmlLinter(AbstractBaseLinter):
    _messages = {"xml-syntax-error": "XML file's syntax is not correct"}

    def __init__(self):
        super().__init__()
        self.invalid_files = set()

    @staticmethod
    def find_tags_with_class(tree, clazz: str, tag: str = "*"):
        return tree.xpath(f"//{tag}[contains(concat(' ', @class, ' '), ' {clazz} ')]")

    def _check_loop(self, config: SchedulerConfiguration, file: str):
        if file in self.invalid_files:
            return

        with open(file, encoding="utf-8") as xml_fd:
            try:
                tree = etree.parse(xml_fd)
            except etree.XMLSyntaxError:
                self.add_message(Message("xml-syntax-error", file))
                self.invalid_files.add(file)
                return

        checks = self.get_active_checks(config.enable, config.disable)
        for check in checks:
            check(tree)
