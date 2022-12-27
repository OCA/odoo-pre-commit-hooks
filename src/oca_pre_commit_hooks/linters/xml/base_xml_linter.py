import functools
import re
from typing import Sequence

from lxml import etree

from oca_pre_commit_hooks.linters.abstract_base_linter import AbstractBaseLinter
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.scheduler_configuration import SchedulerConfiguration


class BaseXmlLinter(AbstractBaseLinter):
    _messages = {"xml-syntax-error": "XML file's syntax is not correct"}
    _checks_disabled_regex = re.compile(re.escape("oca-hooks:disable=") + r"([a-z\-,]+)")

    def __init__(self):
        super().__init__()

    @functools.lru_cache(maxsize=256)
    def get_tag_disabled_checks(self, element) -> Sequence[str]:
        """Retrieve all messages which have been disabled on a specific tag. In order to consider the comment as having
        any effect on the tag it must be a sibling to it and be positioned immediately after it on the same line.
        No line breaks are allowed. Comment MUST start and end on the SAME line.
        """
        try:
            after_sibling = next(element.itersiblings())
        except StopIteration:
            return []

        if after_sibling.tag is not etree.Comment:
            return []
        if element.sourceline != after_sibling.sourceline:
            return []

        match = self._checks_disabled_regex.search(after_sibling.text.strip())
        if not match:
            return []

        return match.group(1).split(",")

    @staticmethod
    def find_tags_with_class(tree, clazz: str, tag: str = "*"):
        return tree.xpath(f"//{tag}[contains(concat(' ', @class, ' '), ' {clazz} ')]")

    def _check_loop(self, config: SchedulerConfiguration, file: str):
        with open(file, encoding="utf-8") as xml_fd:
            try:
                tree = etree.parse(xml_fd)
            except etree.XMLSyntaxError:
                self.add_message(Message("xml-syntax-error", file))
                return

        checks = self.get_active_checks(config.enable, config.disable)
        for check in checks:
            check(tree)
