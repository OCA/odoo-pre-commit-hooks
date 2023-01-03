import functools
import re
from abc import ABC
from typing import Set

from lxml import etree

from oca_pre_commit_hooks.linters.abstract_base_linter import AbstractBaseLinter


class BaseXmlLinter(AbstractBaseLinter, ABC):
    _checks_disabled_regex = re.compile(r"oca-hooks\s*:\s*disable=(([a-z\-]+(,\s*)?)+)")

    @staticmethod
    def _messages_from_match(match: str) -> Set[str]:
        return {message.strip() for message in match.split(",")}

    @classmethod
    @functools.lru_cache(maxsize=256)
    def get_tag_disabled_checks(cls, element) -> Set[str]:
        """Retrieve all messages which have been disabled on a specific tag. In order to consider the comment as having
        any effect on the tag it must be a sibling to it and be positioned immediately after it on the same line.
        No line breaks are allowed. Comment MUST start and end on the SAME line.
        """
        try:
            after_sibling = next(element.itersiblings())
        except StopIteration:
            return set()

        if after_sibling.tag is not etree.Comment:
            return set()
        if element.sourceline != after_sibling.sourceline:
            return set()

        match = cls._checks_disabled_regex.search(after_sibling.text.strip())
        if not match:
            return set()

        return set(cls._messages_from_match(match.group(1)))

    @classmethod
    def get_file_disabled_checks(cls, tree) -> Set[str]:
        """Retrieve all file-wide messages that have been disabled. They are characterized by being a top comment
        with no parent and having <odoo> as their sibling (after)"""

        messages = set()
        comments = tree.xpath("/odoo/preceding-sibling::comment()")
        for comment in comments:
            match = cls._checks_disabled_regex.search(comment.text.strip())
            if match:
                messages.update(cls._messages_from_match(match.group(1)))

        return messages

    @staticmethod
    def find_tags_with_class(tree, clazz: str, tag: str = "*"):
        return tree.xpath(f"//{tag}[contains(concat(' ', @class, ' '), ' {clazz} ')]")

    @staticmethod
    def normalize_xml_id(xml_id: str, module: str) -> str:
        if "." in xml_id:
            return xml_id

        return f"{module}.{xml_id}"
