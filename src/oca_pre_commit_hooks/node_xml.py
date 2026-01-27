import re
from dataclasses import dataclass
from typing import List, Optional

from lxml import etree


@dataclass
class AttributeInfo:
    """Position information for an attribute."""

    name: str
    value: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass
class ElementInfo:
    """Position information for an XML element."""

    name: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    attributes: List[AttributeInfo]
    is_self_closing: bool


class XMLPositionParser:
    """Parser that finds exact positions of elements and attributes."""

    def __init__(self, xml_source: str):
        self.xml_text = xml_source

        self.lines = self.xml_text.split("\n")
        self.elements: List[ElementInfo] = []

    def parse(self) -> List[ElementInfo]:
        """Parse XML and return position information for all elements."""
        tag_pattern = r"<([a-zA-Z_][\w:.-]*)((?:\s+[^>]*?)?)(/?)>"

        for match in re.finditer(tag_pattern, self.xml_text, re.MULTILINE | re.DOTALL):
            tag_name = match.group(1)
            attributes_str = match.group(2)
            is_self_closing = match.group(3) == "/"

            start_pos = match.start()
            start_line, start_col = self._pos_to_line_col(start_pos)

            end_pos = match.end()
            end_line, end_col = self._pos_to_line_col(end_pos)

            attrs = self._parse_attributes(attributes_str, start_pos + len(tag_name) + 1)

            element = ElementInfo(
                name=tag_name,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                attributes=attrs,
                is_self_closing=is_self_closing,
            )

            self.elements.append(element)

        return self.elements

    def _pos_to_line_col(self, pos: int) -> tuple:
        """Convert an absolute position in text to (line, column)."""
        line = 1
        col = 1

        for i, char in enumerate(self.xml_text):
            if i >= pos:
                break
            if char == "\n":
                line += 1
                col = 1
            else:
                col += 1

        return line, col

    def _parse_attributes(self, attr_str: str, base_pos: int) -> List[AttributeInfo]:
        """Parse attributes from a string and return their positions."""
        attributes = []
        attr_pattern = r'([a-zA-Z_][\w:.-]*)\s*=\s*(["\'])((?:(?!\2).)*)\2'

        for match in re.finditer(attr_pattern, attr_str):
            attr_name = match.group(1)
            match.group(2)
            attr_value = match.group(3)

            attr_start_pos = base_pos + match.start()
            attr_end_pos = base_pos + match.end()

            start_line, start_col = self._pos_to_line_col(attr_start_pos)
            end_line, end_col = self._pos_to_line_col(attr_end_pos)

            attr_info = AttributeInfo(
                name=attr_name,
                value=attr_value,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
            )

            attributes.append(attr_info)

        return attributes


class LXMLPositionEnricher:
    """Enriches lxml nodes with precise position information from XMLPositionParser."""

    def __init__(self, xml_source: str):
        self.xml_source = xml_source

        # Parse with lxml
        self.root = etree.fromstring(xml_source.encode("utf-8"))

        # Parse with position parser
        self.position_parser = XMLPositionParser(xml_source)
        self.position_elements = self.position_parser.parse()

        # Create index for matching
        self._create_matching_index()

    def _create_matching_index(self):
        """Create an index to match lxml elements with position elements.
        Uses tag name + document order as key."""
        # Count elements by tag name as we traverse lxml tree
        self.lxml_elements = []
        self._traverse_lxml(self.root)

        # Match lxml elements with position elements by order and tag name
        self.position_map = {}

        # Group position elements by tag name
        pos_by_tag = {}
        for pos_elem in self.position_elements:
            if pos_elem.name not in pos_by_tag:
                pos_by_tag[pos_elem.name] = []
            pos_by_tag[pos_elem.name].append(pos_elem)

        # Group lxml elements by tag name
        lxml_by_tag = {}
        for lxml_elem in self.lxml_elements:
            tag = self._get_tag_name(lxml_elem)
            if tag:  # Skip None values (comments, etc.)
                if tag not in lxml_by_tag:
                    lxml_by_tag[tag] = []
                lxml_by_tag[tag].append(lxml_elem)

        # Match elements with same tag name by order
        for tag_name in lxml_by_tag:
            if tag_name in pos_by_tag:
                lxml_list = lxml_by_tag[tag_name]
                pos_list = pos_by_tag[tag_name]

                # Match by order (assumes same document structure)
                for i in range(min(len(lxml_list), len(pos_list))):
                    lxml_elem = lxml_list[i]
                    pos_elem = pos_list[i]

                    # Verify attributes match for extra safety
                    if self._attributes_match(lxml_elem, pos_elem):
                        self.position_map[id(lxml_elem)] = pos_elem

    def _traverse_lxml(self, element):
        """Traverse lxml tree in document order."""
        # Only add actual elements (not comments, processing instructions, etc.)
        if isinstance(element.tag, str):
            self.lxml_elements.append(element)

        for child in element:
            self._traverse_lxml(child)

    def _get_tag_name(self, element) -> str:
        """Get tag name from lxml element, handling namespaces."""
        tag = element.tag

        # Skip non-element nodes (comments, processing instructions, etc.)
        if not isinstance(tag, str):
            return None

        if "}" in tag:
            # Remove namespace: {http://example.com}tag -> tag
            tag = tag.split("}")[1]
        return tag

    def _attributes_match(self, lxml_elem, pos_elem: ElementInfo) -> bool:
        """Check if attributes match between lxml element and position element.
        Returns True if they match or if comparison is inconclusive.
        """
        lxml_attrs = dict(lxml_elem.attrib)
        pos_attrs = {attr.name: attr.value for attr in pos_elem.attributes}

        # If both have no attributes, they match
        if not lxml_attrs and not pos_attrs:
            return True

        # If attribute counts differ, they don't match
        if len(lxml_attrs) != len(pos_attrs):
            return False

        # Check if all attributes match
        for key, value in lxml_attrs.items():
            if key not in pos_attrs or pos_attrs[key] != value:
                return False

        return True

    def get_position_info(self, lxml_element) -> Optional[ElementInfo]:
        """Get position information for an lxml element.

        Args:
            lxml_element: An lxml Element object

        Returns:
            ElementInfo with position data, or None if not found
        """
        return self.position_map.get(id(lxml_element))

    def enrich_element(self, lxml_element):
        """Add position information as attributes to an lxml element.
        Adds: _start_line, _start_col, _end_line, _end_col
        """
        pos_info = self.get_position_info(lxml_element)
        if pos_info:
            lxml_element.set("_start_line", str(pos_info.start_line))
            lxml_element.set("_start_col", str(pos_info.start_col))
            lxml_element.set("_end_line", str(pos_info.end_line))
            lxml_element.set("_end_col", str(pos_info.end_col))

    def enrich_all(self):
        """Add position information to all elements in the tree."""
        for elem in self.lxml_elements:
            self.enrich_element(elem)


def demo():
    """Demonstration of the enricher."""
    xml_test = """<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <!-- Test comment -->
    <template id="test_template_15" name="Test Template 15">
        <div>
            <span t-esc="price" />
            <span t-raw="amount" />
        </div>
    </template>
    <template id="test_template_15_2" name="test_template_15_2">
        <div class="mt32">
            <div class="text-left">
                <strong>Name <t
                    t-esc="o.name"
                />
                </strong>
            </div>
        </div>
    </template>
</odoo>"""

    print("=== lxml Position Enricher Demo ===\n")

    # Create enricher
    enricher = LXMLPositionEnricher(xml_test)

    print("Matching lxml elements with position data...\n")
    print("=" * 70)

    # Iterate through lxml tree and show position info
    for elem in enricher.lxml_elements:
        tag = enricher._get_tag_name(elem)
        pos_info = enricher.get_position_info(elem)

        if pos_info:
            attrs = ", ".join([f"{k}='{v}'" for k, v in elem.attrib.items()])
            attrs_str = f" [{attrs}]" if attrs else ""

            print(f"\n<{tag}>{attrs_str}")
            print(f"  lxml sourceline: {elem.sourceline}")
            print(f"  Precise position:")
            print(f"    Start: line {pos_info.start_line}, col {pos_info.start_col}")
            print(f"    End:   line {pos_info.end_line}, col {pos_info.end_col}")

            if pos_info.attributes:
                print(f"  Attributes with positions:")
                for attr in pos_info.attributes:
                    print(
                        f"    • {attr.name}: ({attr.start_line},{attr.start_col}) → ({attr.end_line},{attr.end_col})"
                    )

    print("\n" + "=" * 70)
    print("\nExample: Enrich elements with position attributes")
    print("=" * 70)

    enricher.enrich_all()

    # Show enriched XML snippet
    for elem in list(enricher.lxml_elements)[:3]:
        tag = enricher._get_tag_name(elem)
        print(f"\n<{tag}>")
        for key, value in elem.attrib.items():
            if key.startswith("_"):
                print(f"  {key}: {value}")


if __name__ == "__main__":
    demo()


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
        # Determine the search start line
        if (node_previous := self.node.getprevious()) is not None:
            search_start_line = node_previous.sourceline + 1
        elif (node_parent := self.node.getparent()) is not None:
            # Start from parent line (not +1) because child tags can be on same line as parent
            search_start_line = node_parent.sourceline
        else:
            search_start_line = 2  # first element and it is the root

        search_end_line = self.node.sourceline
        node_tag = self.node.tag.encode() if isinstance(self.node.tag, str) else self.node.tag

        # Read all lines from file
        with open(self.filename, "rb") as f_content:
            all_lines = list((i, line) for i, line in enumerate(f_content, start=1))

        # Find the actual node start by looking for the tag
        node_start_idx = None
        node_start_col = 0  # Column position within the line

        # When there are multiple tags on the same line, we need to find the RIGHT one
        # We'll collect all candidates and use additional heuristics
        candidates = []

        for idx, (no_line, line) in enumerate(all_lines):
            if search_start_line <= no_line <= search_end_line:
                # Look for the tag anywhere in the line, not just at the start
                tag_pattern = b"<" + node_tag
                tag_pos = 0

                # Find ALL occurrences of the tag in this line
                while True:
                    tag_pos = line.find(tag_pattern, tag_pos)
                    if tag_pos == -1:
                        break

                    # Verify it's actually a tag start (followed by space, >, or /)
                    check_pos = tag_pos + len(tag_pattern)
                    is_valid = False

                    if check_pos >= len(line):
                        # Tag at end of line is valid
                        is_valid = True
                    else:
                        next_char = line[check_pos : check_pos + 1]
                        # Valid tag if followed by space, >, /, or newline
                        if next_char in (b" ", b">", b"/", b"\n", b"\r"):
                            is_valid = True

                    if is_valid:
                        candidates.append({"idx": idx, "line_no": no_line, "col": tag_pos, "line": line})

                    tag_pos += 1

        # Choose the best candidate
        if candidates:
            # If we only have one candidate, use it
            if len(candidates) == 1:
                best = candidates[0]
                node_start_idx = best["idx"]
                node_start_col = best["col"]
                self.start_sourceline = best["line_no"]
            else:
                # Multiple candidates - need to find the right one
                # Strategy: use node attributes to identify the correct tag
                best = None

                # Get the first attribute of the node if it exists
                node_attrib_key = None
                if self.node.attrib:
                    node_attrib_key = list(self.node.attrib.keys())[0]

                # Try to match by attribute
                if node_attrib_key:
                    attr_pattern = f"{node_attrib_key}=".encode()
                    for candidate in candidates:
                        # Look in the line and following lines for this attribute
                        idx = candidate["idx"]
                        # Check current line from the tag position
                        search_text = candidate["line"][candidate["col"] :]
                        # Also check next few lines (in case attributes span lines)
                        for i in range(idx, min(idx + 5, len(all_lines))):
                            if i > idx:
                                search_text += all_lines[i][1]

                        if attr_pattern in search_text:
                            best = candidate
                            break

                # If we didn't find by attribute, use line number heuristic
                if best is None:
                    # Prefer candidates on the target line (node.sourceline)
                    candidates_on_target_line = [c for c in candidates if c["line_no"] == search_end_line]

                    if candidates_on_target_line:
                        # If multiple on target line, prefer the last one
                        best = candidates_on_target_line[-1]
                    else:
                        # Use the last candidate overall
                        best = candidates[-1]

                node_start_idx = best["idx"]
                node_start_col = best["col"]
                self.start_sourceline = best["line_no"]

        if node_start_idx is None:
            # Fallback: use search_end_line
            self.start_sourceline = search_end_line
            for idx, (no_line, _line) in enumerate(all_lines):
                if no_line == search_end_line:
                    node_start_idx = idx
                    break

        # Find the actual node end
        node_end_idx = node_start_idx
        node_end_col = None  # Column position where node ends
        self.end_sourceline = self.start_sourceline

        # Track nesting level to handle cases where parent and child have same tag
        nesting_level = 0

        for idx in range(node_start_idx, len(all_lines)):
            no_line, line = all_lines[idx]

            if idx == node_start_idx:
                # For the starting line, only look at content from node_start_col onwards
                relevant_line = line[node_start_col:]

                # Check if self-closing on same line
                self_close_pos = relevant_line.find(b"/>")
                if self_close_pos != -1:
                    # Verify this is the closing for our tag, not a nested one
                    # Simple check: see if there's another opening tag between start and close
                    between = relevant_line[:self_close_pos]
                    # Count opening tags in between
                    temp_count = between.count(b"<" + node_tag)
                    if temp_count == 1:  # Only our opening tag
                        node_end_idx = idx
                        node_end_col = node_start_col + self_close_pos + 2
                        self.end_sourceline = no_line
                        break

                # Check if opening and closing tag on same line
                close_tag = b"</" + node_tag + b">"
                close_pos = relevant_line.find(close_tag)
                if close_pos != -1:
                    node_end_idx = idx
                    node_end_col = node_start_col + close_pos + len(close_tag)
                    self.end_sourceline = no_line
                    break

                # Node continues beyond this line
                nesting_level = 1
            else:
                # Look for closing patterns
                stripped_line = line.lstrip()

                # Check for self-closing continuation (when tag opened in previous line)
                # This handles cases like:
                # <span
                #    attr="value"
                # />
                if b"/>" in line:
                    # Check if this is a standalone /> (not part of a new tag)
                    # by seeing if the line starts with /> or has /> after attributes
                    if stripped_line.startswith(b"/>") or (
                        b">" not in line[: line.find(b"/>")] if b"/>" in line else False
                    ):
                        node_end_idx = idx
                        node_end_col = line.find(b"/>") + 2
                        self.end_sourceline = no_line
                        nesting_level -= 1
                        if not nesting_level:
                            break

                # Look for closing tag
                close_tag = b"</" + node_tag + b">"
                if close_tag in line:
                    node_end_idx = idx
                    node_end_col = line.find(close_tag) + len(close_tag)
                    self.end_sourceline = no_line
                    nesting_level -= 1
                    if not nesting_level:
                        break

                # Count any new opening tags to track nesting
                pos = 0
                while True:
                    pos = line.find(b"<" + node_tag, pos)
                    if pos == -1:
                        break
                    # Verify it's a real opening tag
                    check_pos = pos + len(node_tag) + 1
                    if check_pos < len(line):
                        next_char = line[check_pos : check_pos + 1]
                        if next_char in (b" ", b">", b"/", b"\n", b"\r"):
                            nesting_level += 1
                    pos += 1

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
            elif idx == node_start_idx:
                # For the start line, split at the column position
                self.content_before += line[:node_start_col]

                if idx == node_end_idx:
                    # Node starts and ends on same line
                    self.content_node += line[node_start_col:node_end_col]
                    self.content_after += line[node_end_col:]
                else:
                    # Node continues to next line(s)
                    self.content_node += line[node_start_col:]
            elif node_start_idx < idx < node_end_idx:
                # Full lines that are part of the node
                self.content_node += line
            elif idx == node_end_idx and idx != node_start_idx:
                # Last line of the node
                self.content_node += line[:node_end_col]
                self.content_after += line[node_end_col:]
            elif idx > node_end_idx:
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


import re
from dataclasses import dataclass
from typing import List, Optional

from lxml import etree


@dataclass
class AttributeInfo:
    """Position information for an attribute."""

    name: str
    value: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass
class ElementInfo:
    """Position information for an XML element."""

    name: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    attributes: List[AttributeInfo]
    is_self_closing: bool


class XMLPositionParser:
    """Parser that finds exact positions of elements and attributes."""

    def __init__(self, xml_content: bytes):
        """
        Initialize the parser.

        Args:
            xml_content: XML content as bytes
        """
        self.xml_text = xml_content.decode("utf-8")
        self.lines = self.xml_text.split("\n")
        self.elements: List[ElementInfo] = []

    def parse(self) -> List[ElementInfo]:
        """Parse XML and return position information for all elements."""
        tag_pattern = r"<([a-zA-Z_][\w:.-]*)((?:\s+[^>]*?)?)(/?)>"

        for match in re.finditer(tag_pattern, self.xml_text, re.MULTILINE | re.DOTALL):
            tag_name = match.group(1)
            attributes_str = match.group(2)
            is_self_closing = match.group(3) == "/"

            start_pos = match.start()
            start_line, start_col = self._pos_to_line_col(start_pos)

            end_pos = match.end()
            end_line, end_col = self._pos_to_line_col(end_pos)

            attrs = self._parse_attributes(attributes_str, start_pos + len(tag_name) + 1)

            element = ElementInfo(
                name=tag_name,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                attributes=attrs,
                is_self_closing=is_self_closing,
            )

            self.elements.append(element)

        return self.elements

    def _pos_to_line_col(self, pos: int) -> tuple:
        """Convert an absolute position in text to (line, column)."""
        line = 1
        col = 1

        for i, char in enumerate(self.xml_text):
            if i >= pos:
                break
            if char == "\n":
                line += 1
                col = 1
            else:
                col += 1

        return line, col

    def _parse_attributes(self, attr_str: str, base_pos: int) -> List[AttributeInfo]:
        """Parse attributes from a string and return their positions."""
        attributes = []
        attr_pattern = r'([a-zA-Z_][\w:.-]*)\s*=\s*(["\'])((?:(?!\2).)*)\2'

        for match in re.finditer(attr_pattern, attr_str):
            attr_name = match.group(1)
            match.group(2)
            attr_value = match.group(3)

            attr_start_pos = base_pos + match.start()
            attr_end_pos = base_pos + match.end()

            start_line, start_col = self._pos_to_line_col(attr_start_pos)
            end_line, end_col = self._pos_to_line_col(attr_end_pos)

            attr_info = AttributeInfo(
                name=attr_name,
                value=attr_value,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
            )

            attributes.append(attr_info)

        return attributes


class PositionElement(etree.ElementBase):
    """
    Custom lxml Element class that includes position information.

    Additional attributes:
        - start_line: Line where element starts
        - start_col: Column where element starts
        - end_line: Line where element ends
        - end_col: Column where element ends
        - is_self_closing: Whether element is self-closing
        - position_attributes: List of AttributeInfo objects
    """

    # Use __slots__ to store position data directly in the instance
    # This works better with lxml's internal structure
    __slots__ = ()

    def _set_position_data(self, start_line, start_col, end_line, end_col, is_self_closing, position_attributes):
        """Internal method to set position data."""
        # Store in a special namespace to avoid conflicts with XML attributes
        self.set("_pos_start_line", str(start_line))
        self.set("_pos_start_col", str(start_col))
        self.set("_pos_end_line", str(end_line))
        self.set("_pos_end_col", str(end_col))
        self.set("_pos_is_self_closing", str(is_self_closing))
        # Store position_attributes in a way that survives
        # We'll use the element's __dict__ if available, or fall back to a global dict
        try:
            object.__setattr__(self, "_pos_attrs_data", position_attributes)
        except (AttributeError, TypeError):
            # Fallback: store in element's tail (not ideal but works)
            pass

    @property
    def start_line(self) -> Optional[int]:
        """Line where element starts."""
        val = self.get("_pos_start_line")
        return int(val) if val and val != "None" else None

    @property
    def start_col(self) -> Optional[int]:
        """Column where element starts."""
        val = self.get("_pos_start_col")
        return int(val) if val and val != "None" else None

    @property
    def end_line(self) -> Optional[int]:
        """Line where element ends."""
        val = self.get("_pos_end_line")
        return int(val) if val and val != "None" else None

    @property
    def end_col(self) -> Optional[int]:
        """Column where element ends."""
        val = self.get("_pos_end_col")
        return int(val) if val and val != "None" else None

    @property
    def is_self_closing(self) -> Optional[bool]:
        """Whether element is self-closing."""
        val = self.get("_pos_is_self_closing")
        if val is None or val == "None":
            return None
        return val == "True"

    @property
    def position_attributes(self) -> List[AttributeInfo]:
        """List of attributes with position information."""
        try:
            return object.__getattribute__(self, "_pos_attrs_data")
        except AttributeError:
            return []


class LXMLPositionEnricher:
    """
    Custom lxml parser that enriches elements with position information.

    Usage:
        enricher = LXMLPositionEnricher(xml_content)
        root = enricher.root

        # Now you can access position info:
        element = root.xpath("//record")[0]
        print(element.start_line)
        print(element.start_col)
        print(element.is_self_closing)
        print(element.position_attributes[0].start_line)
    """

    def __init__(self, xml_content: bytes):
        """
        Initialize the enricher.

        Args:
            xml_content: XML content as bytes
        """
        self.xml_content = xml_content

        # Create custom parser with our PositionElement class
        parser = etree.XMLParser()
        lookup = etree.ElementDefaultClassLookup(element=PositionElement)
        parser.set_element_class_lookup(lookup)

        # Parse with lxml using custom element class
        self.root = etree.fromstring(xml_content, parser)

        # Parse with position parser
        self.position_parser = XMLPositionParser(xml_content)
        self.position_elements = self.position_parser.parse()

        # Enrich elements with position data
        self._enrich_elements()

    def _enrich_elements(self):
        """Match and enrich lxml elements with position information."""
        # Collect all lxml elements in document order
        lxml_elements = []
        self._traverse_lxml(self.root, lxml_elements)

        # Debug: Print what we found
        print(f"DEBUG: Found {len(lxml_elements)} lxml elements")
        print(f"DEBUG: Found {len(self.position_elements)} position elements")

        # Group position elements by tag name
        pos_by_tag = {}
        for pos_elem in self.position_elements:
            if pos_elem.name not in pos_by_tag:
                pos_by_tag[pos_elem.name] = []
            pos_by_tag[pos_elem.name].append(pos_elem)

        print(f"DEBUG: Position elements by tag: {list(pos_by_tag.keys())}")

        # Group lxml elements by tag name
        lxml_by_tag = {}
        for lxml_elem in lxml_elements:
            tag = self._get_tag_name(lxml_elem)
            if tag:
                if tag not in lxml_by_tag:
                    lxml_by_tag[tag] = []
                lxml_by_tag[tag].append(lxml_elem)

        print(f"DEBUG: lxml elements by tag: {list(lxml_by_tag.keys())}")

        # Match and enrich elements with same tag name by order
        for tag_name in lxml_by_tag:
            if tag_name in pos_by_tag:
                lxml_list = lxml_by_tag[tag_name]
                pos_list = pos_by_tag[tag_name]

                print(f"DEBUG: Matching {len(lxml_list)} lxml <{tag_name}> with {len(pos_list)} position <{tag_name}>")

                for i in range(min(len(lxml_list), len(pos_list))):
                    lxml_elem = lxml_list[i]
                    pos_elem = pos_list[i]

                    # Debug attributes
                    lxml_attrs = dict(lxml_elem.attrib)
                    pos_attrs = {attr.name: attr.value for attr in pos_elem.attributes}
                    print(f"  DEBUG: Comparing element {i}:")
                    print(f"    lxml attrs: {lxml_attrs}")
                    print(f"    pos attrs: {pos_attrs}")

                    # Verify attributes match
                    if self._attributes_match(lxml_elem, pos_elem):
                        print(f"    ✓ MATCH! Setting position data")
                        # Set position information using the custom method
                        lxml_elem._set_position_data(
                            start_line=pos_elem.start_line,
                            start_col=pos_elem.start_col,
                            end_line=pos_elem.end_line,
                            end_col=pos_elem.end_col,
                            is_self_closing=pos_elem.is_self_closing,
                            position_attributes=pos_elem.attributes,
                        )
                    else:
                        print(f"    ✗ NO MATCH")

    def _traverse_lxml(self, element, elements_list):
        """Traverse lxml tree in document order."""
        if isinstance(element.tag, str):
            elements_list.append(element)

        for child in element:
            self._traverse_lxml(child, elements_list)

    def _get_tag_name(self, element) -> Optional[str]:
        """Get tag name from lxml element, handling namespaces."""
        tag = element.tag

        # Skip non-element nodes
        if not isinstance(tag, str):
            return None

        if "}" in tag:
            # Remove namespace: {http://example.com}tag -> tag
            tag = tag.split("}")[1]
        return tag

    def _attributes_match(self, lxml_elem, pos_elem: ElementInfo) -> bool:
        """Check if attributes match between lxml element and position element."""
        lxml_attrs = dict(lxml_elem.attrib)
        pos_attrs = {attr.name: attr.value for attr in pos_elem.attributes}

        # If both have no attributes, they match
        if not lxml_attrs and not pos_attrs:
            return True

        # If attribute counts differ, they don't match
        if len(lxml_attrs) != len(pos_attrs):
            return False

        # Check if all attributes match
        for key, value in lxml_attrs.items():
            if key not in pos_attrs or pos_attrs[key] != value:
                return False

        return True


def demo():
    """Demonstration of the enriched lxml parser."""
    xml_test = b"""<?xml version="1.0" encoding="UTF-8" ?>
<odoo>
    <!-- Test comment -->
    <template id="test_template_15" name="Test Template 15">
        <div>
            <span t-esc="price" />
            <span t-raw="amount" />
        </div>
    </template>
    <template id="test_template_15_2" name="test_template_15_2">
        <div class="mt32">
            <div class="text-left">
                <strong>Name <t
                    t-esc="o.name"
                />
                </strong>
            </div>
        </div>
    </template>
</odoo>"""

    print("=== Enhanced lxml Parser Demo ===\n")
    print("Creating enriched lxml tree...")

    # Parse XML with position enrichment
    enricher = LXMLPositionEnricher(xml_test)
    root = enricher.root

    print(f"Root element: <{root.tag}>\n")
    print("=" * 70)

    # Example 1: Access position info directly
    print("\nExample 1: Direct property access")
    print("-" * 70)

    templates = root.xpath("//template")
    for template in templates:
        print(f"\n<{template.tag} id='{template.get('id')}'>")
        print(f"  start_line: {template.start_line}")
        print(f"  start_col: {template.start_col}")
        print(f"  end_line: {template.end_line}")
        print(f"  end_col: {template.end_col}")
        print(f"  is_self_closing: {template.is_self_closing}")

        if template.position_attributes:
            print(f"  Attributes with positions:")
            for attr in template.position_attributes:
                print(f"    • {attr.name}='{attr.value}'")
                print(f"      ({attr.start_line},{attr.start_col}) → ({attr.end_line},{attr.end_col})")

    # Example 2: Find specific element and check position
    print("\n" + "=" * 70)
    print("\nExample 2: Find <t> element with t-esc attribute")
    print("-" * 70)

    t_elements = root.xpath("//t[@t-esc]")
    if t_elements:
        t_elem = t_elements[0]
        print(f"\nFound: <{t_elem.tag}>")
        print(f"  Position: ({t_elem.start_line},{t_elem.start_col}) → ({t_elem.end_line},{t_elem.end_col})")
        print(f"  Self-closing: {t_elem.is_self_closing}")
        print(f"  Attributes:")
        for attr in t_elem.position_attributes:
            print(f"    {attr.name}='{attr.value}' @ line {attr.start_line}, col {attr.start_col}")

    # Example 3: Iterate all span elements
    print("\n" + "=" * 70)
    print("\nExample 3: All <span> elements")
    print("-" * 70)

    for span in root.xpath("//span"):
        attrs = ", ".join([f"{k}='{v}'" for k, v in span.attrib.items()])
        print(f"\n<span {attrs} />")
        print(f"  Lines: {span.start_line} → {span.end_line}")
        print(f"  Columns: {span.start_col} → {span.end_col}")

    # Example 4: Demonstrate it's still a regular lxml element
    print("\n" + "=" * 70)
    print("\nExample 4: Still works as regular lxml element")
    print("-" * 70)

    print(f"\nCan use all lxml methods:")
    print(f"  root.tag: {root.tag}")
    print(f"  root.getchildren() count: {len(root.getchildren())}")
    print(f"  root.xpath('//div') count: {len(root.xpath('//div'))}")
    print(f"  isinstance(root, etree._Element): {isinstance(root, etree._Element)}")
    print(f"  isinstance(root, PositionElement): {isinstance(root, PositionElement)}")


if __name__ == "__main__":
    demo()
