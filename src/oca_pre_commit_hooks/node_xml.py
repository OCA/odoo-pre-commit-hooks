# Based on https://github.com/mitsuhiko/sloppy-xml-py
from dataclasses import dataclass


@dataclass(frozen=True)
class XMLAttributeSpan:
    name: str
    value_start: int
    value_end: int
    name_start: int
    name_end: int
    attr_end: int


@dataclass(frozen=True)
class XMLStartTag:
    tag: str
    start: int
    name_end: int
    end: int
    line: int
    attrs: tuple[XMLAttributeSpan, ...]

    def get_attr(self, attr_name):
        for attr in self.attrs:
            if attr.name == attr_name:
                return attr
        return None


class XMLStartTagLocator:
    """Locate opening tags and attribute spans without reformatting the file."""

    def __init__(self, filename, tree):
        self.filename = filename
        with open(filename, "rb") as f_content:
            self.content = f_content.read()
        self.tags = self._scan_start_tags(self.content)
        self._element_tags = {}
        self._map_tree(tree)

    @staticmethod
    def _consume_until(content, start, needle):
        end = content.find(needle, start)
        if end == -1:
            return len(content)
        return end + len(needle)

    @classmethod
    def _scan_start_tags(cls, content):  # noqa: C901 pylint: disable=too-complex
        tags = []
        i = 0
        line = 1
        content_len = len(content)

        while i < content_len:
            byte = content[i : i + 1]
            if byte == b"\n":
                line += 1
                i += 1
                continue
            if byte != b"<":
                i += 1
                continue

            if content.startswith(b"<!--", i):
                new_i = cls._consume_until(content, i + 4, b"-->")
                line += content[i:new_i].count(b"\n")
                i = new_i
                continue
            if content.startswith(b"<?", i):
                new_i = cls._consume_until(content, i + 2, b"?>")
                line += content[i:new_i].count(b"\n")
                i = new_i
                continue
            if content.startswith(b"<![CDATA[", i):
                new_i = cls._consume_until(content, i + 9, b"]]>")
                line += content[i:new_i].count(b"\n")
                i = new_i
                continue
            if content.startswith(b"</", i):
                new_i = cls._consume_until(content, i + 2, b">")
                line += content[i:new_i].count(b"\n")
                i = new_i
                continue
            if content.startswith(b"<!", i):
                new_i = cls._consume_until(content, i + 2, b">")
                line += content[i:new_i].count(b"\n")
                i = new_i
                continue

            tag_line = line
            tag_start = i
            i += 1
            name_start = i
            while i < content_len and content[i : i + 1] not in b" \t\r\n/>":
                i += 1
            tag_name = content[name_start:i].decode("utf-8", errors="replace")
            tag_name_end = i
            attrs = []

            while i < content_len:
                while i < content_len and content[i : i + 1] in b" \t\r\n":
                    if content[i : i + 1] == b"\n":
                        line += 1
                    i += 1
                if i >= content_len:
                    break
                if content.startswith(b"/>", i):
                    i += 2
                    break
                if content[i : i + 1] == b">":
                    i += 1
                    break

                attr_name_start = i
                while i < content_len and content[i : i + 1] not in b" \t\r\n=/>":
                    i += 1
                attr_name_end = i
                attr_name = content[attr_name_start:attr_name_end].decode("utf-8", errors="replace")

                while i < content_len and content[i : i + 1] in b" \t\r\n":
                    if content[i : i + 1] == b"\n":
                        line += 1
                    i += 1
                if i < content_len and content[i : i + 1] == b"=":
                    i += 1
                while i < content_len and content[i : i + 1] in b" \t\r\n":
                    if content[i : i + 1] == b"\n":
                        line += 1
                    i += 1

                if i >= content_len or content[i : i + 1] not in (b'"', b"'"):
                    continue
                quote = content[i : i + 1]
                i += 1
                value_start = i
                while i < content_len:
                    if content[i : i + 1] == b"\n":
                        line += 1
                    if content[i : i + 1] == quote:
                        value_end = i
                        i += 1
                        break
                    i += 1

                attrs.append(XMLAttributeSpan(attr_name, value_start, value_end, attr_name_start, attr_name_end, i))

            tags.append(XMLStartTag(tag_name, tag_start, tag_name_end, i, tag_line, tuple(attrs)))

        return tags

    def _map_tree(self, tree):
        tag_iter = iter(self.tags)
        for element in tree.getroot().iter():
            if not isinstance(getattr(element, "tag", None), str):
                continue
            tag_info = next(tag_iter, None)
            if tag_info is None:
                break
            self._element_tags[tree.getpath(element)] = tag_info

    def get_tag(self, element):
        return self._element_tags.get(element.getroottree().getpath(element))

    def get_attr(self, element, attr_name):
        tag_info = self.get_tag(element)
        if not tag_info:
            return None
        return tag_info.get_attr(attr_name)

    def rewrite_start_tag(
        self, content, element, attr_name_replacements=None, attr_value_replacements=None, first_attr=None
    ):
        tag_info = self.get_tag(element)
        if not tag_info:
            return content

        attr_name_replacements = attr_name_replacements or {}
        attr_value_replacements = attr_value_replacements or {}
        attrs = list(tag_info.attrs)
        if not attrs:
            return content

        open_part = content[tag_info.start : tag_info.name_end]
        cursor = tag_info.name_end
        spaces = []
        attr_chunks = {}

        for attr in attrs:
            spaces.append(content[cursor : attr.name_start])
            chunk = bytearray(content[attr.name_start : attr.attr_end])
            if attr.name in attr_name_replacements:
                new_name = attr_name_replacements[attr.name]
                chunk[: len(attr.name)] = new_name
            if attr.name in attr_value_replacements:
                value_rel_start = attr.value_start - attr.name_start
                value_rel_end = attr.value_end - attr.name_start
                chunk[value_rel_start:value_rel_end] = attr_value_replacements[attr.name]
            attr_chunks[attr.name] = bytes(chunk)
            cursor = attr.attr_end

        close_part = content[cursor : tag_info.end]
        ordered_attrs = attrs
        if first_attr:
            target_attr = next((attr for attr in attrs if attr.name == first_attr), None)
            if target_attr and attrs[0].name != first_attr:
                ordered_attrs = [target_attr] + [attr for attr in attrs if attr.name != first_attr]

        rebuilt = open_part
        for idx, attr in enumerate(ordered_attrs):
            rebuilt += spaces[idx] + attr_chunks[attr.name]
        rebuilt += close_part
        return content[: tag_info.start] + rebuilt + content[tag_info.end :]


class NodeContent:
    """Represents the content and metadata of an XML node."""

    def __init__(self, filename, node):
        """Initialize by reading and parsing the node from the file.

        Args:
            filename: Path to the XML file
            node: lxml node element to extract
        """
        self.filename = filename
        self.node = node

        # Initialize attributes
        self.content_before = b""
        self.content_node = b""
        self.content_after = b""
        self.node_comment = b""
        self.start_sourceline = None
        self.end_sourceline = None

        # Read and parse the node
        self._read_node()

    def _read_node(self):  # noqa:C901 pylint:disable=too-complex
        """Internal method to read the content of the file and extract node information."""
        # TODO: Get the sourceline of a particular attribute
        # Determine the search start line
        if (node_previous := self.node.getprevious()) is not None:
            search_start_line = node_previous.sourceline + 1
        elif (node_parent := self.node.getparent()) is not None:
            search_start_line = node_parent.sourceline + 1
        else:
            search_start_line = 2  # first element and it is the root

        search_end_line = self.node.sourceline
        node_tag = self.node.tag.encode() if isinstance(self.node.tag, str) else self.node.tag

        # Read all lines from file
        with open(self.filename, "rb") as f_content:
            all_lines = list((i, line) for i, line in enumerate(f_content, start=1))

        # Find the actual node start by looking for the tag
        node_start_idx = None
        for idx, (no_line, line) in enumerate(all_lines):
            if search_start_line <= no_line <= search_end_line:
                stripped_line = line.lstrip()
                if stripped_line.startswith(b"<" + node_tag):
                    node_start_idx = idx
                    self.start_sourceline = no_line
                    break

        if node_start_idx is None:
            # Fallback: use search_end_line
            self.start_sourceline = search_end_line
            for idx, (no_line, _line) in enumerate(all_lines):
                if no_line == search_end_line:
                    node_start_idx = idx
                    break

        # Find the actual node end
        node_end_idx = node_start_idx
        self.end_sourceline = self.start_sourceline

        for idx in range(node_start_idx, len(all_lines)):
            no_line, line = all_lines[idx]
            stripped_line = line.lstrip()

            if idx == node_start_idx:
                # Check if self-closing or single-line
                if b"/>" in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
                if b"<" + node_tag in line and b"</" + node_tag in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
            else:
                # Look for closing tag
                if b"</" + node_tag + b">" in line or b"</" + node_tag + b" " in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
                if b"/>" in stripped_line and not stripped_line.startswith(b"<"):
                    # Self-closing continuation
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break

        # Look backwards from node start for comment
        for idx in range(node_start_idx - 1, -1, -1):
            no_line, line = all_lines[idx]
            stripped_line = line.lstrip()

            # Skip empty lines
            if stripped_line in (b"", b"\n", b"\r\n"):
                continue

            # Check if it's a comment end
            if b"-->" in stripped_line:
                # Found comment end, now find comment start
                comment_lines = []
                for comment_idx in range(idx, -1, -1):
                    _comment_no_line, comment_line = all_lines[comment_idx]
                    comment_lines.insert(0, comment_line)
                    if b"<!--" in comment_line:
                        self.node_comment = b"".join(comment_lines)
                        break
            break

        # Build content_before, content_node, content_after
        for idx, (_no_line, line) in enumerate(all_lines):
            if idx < node_start_idx:
                # Skip comment lines if they were captured
                if self.node_comment and line in self.node_comment:
                    self.content_before += line
                    continue
                self.content_before += line
            elif node_start_idx <= idx <= node_end_idx:
                self.content_node += line
            else:
                self.content_after += line

        # Remove comment from content_before if present
        if self.node_comment:
            # Find and remove the exact comment sequence
            comment_start = self.content_before.rfind(self.node_comment)
            if comment_start != -1:
                self.content_before = (
                    self.content_before[:comment_start] + self.content_before[comment_start + len(self.node_comment) :]
                )

    def __str__(self):
        """Return the complete content in order."""
        return (self.content_before + self.node_comment + self.content_node + self.content_after).decode(
            "utf-8", errors="replace"
        )

    def __bytes__(self):
        """Return the complete content as bytes."""
        return self.content_before + self.node_comment + self.content_node + self.content_after

    def __repr__(self):
        return (
            f"NodeContent(start_line={self.start_sourceline}, "
            f"end_line={self.end_sourceline}, "
            f"has_comment={len(self.node_comment) > 0})"
        )
