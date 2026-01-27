import html
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
        # Robust pattern for multi-line tags
        # Matches: <tagname ... > or <tagname ... />
        # Uses greedy matching to capture everything until the closing >
        tag_pattern = r"<([a-zA-Z_][\w:.-]*)(.*?)(/?)>"

        for match in re.finditer(tag_pattern, self.xml_text, re.MULTILINE | re.DOTALL):
            tag_name = match.group(1)
            attributes_str = match.group(2)
            is_self_closing = match.group(3) == "/"

            # Skip if this looks like a closing tag
            if attributes_str.strip().startswith("/"):
                continue

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

        # Pattern that properly handles escaped quotes inside attribute values
        # Matches double quotes: name="value with &quot; inside"
        attr_pattern_double = r'([a-zA-Z_][\w:.-]*)\s*=\s*"([^"]*(?:&quot;[^"]*)*)"'
        # Matches single quotes: name='value with &apos; inside'
        attr_pattern_single = r"([a-zA-Z_][\w:.-]*)\s*=\s*'([^']*(?:&apos;[^']*)*)'"

        # Try double quotes first
        for match in re.finditer(attr_pattern_double, attr_str, re.DOTALL):
            attr_name = match.group(1)
            attr_value_raw = match.group(2)

            # Decode HTML entities to match what lxml does (&quot; -> ", &amp; -> &, etc.)
            attr_value = html.unescape(attr_value_raw)

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

        # Try single quotes
        for match in re.finditer(attr_pattern_single, attr_str, re.DOTALL):
            attr_name = match.group(1)
            attr_value_raw = match.group(2)

            # Decode HTML entities
            attr_value = html.unescape(attr_value_raw)

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

    Additional properties:
        - start_line: Line where element starts
        - start_col: Column where element starts
        - end_line: Line where element ends
        - end_col: Column where element ends
        - is_self_closing: Whether element is self-closing
        - position_attributes: List of AttributeInfo objects
    """

    __slots__ = ()

    def _set_position_data(self, start_line, start_col, end_line, end_col, is_self_closing, position_attributes):
        """Internal method to set position data."""
        self.set("_pos_start_line", str(start_line))
        self.set("_pos_start_col", str(start_col))
        self.set("_pos_end_line", str(end_line))
        self.set("_pos_end_col", str(end_col))
        self.set("_pos_is_self_closing", str(is_self_closing))

        # Try to store position_attributes directly
        try:
            object.__setattr__(self, "_pos_attrs_data", position_attributes)
        except (AttributeError, TypeError):
            pass

        # Also serialize as JSON for reliable storage
        import json

        attrs_json = json.dumps(
            [
                {
                    "name": attr.name,
                    "value": attr.value,
                    "start_line": attr.start_line,
                    "start_col": attr.start_col,
                    "end_line": attr.end_line,
                    "end_col": attr.end_col,
                }
                for attr in position_attributes
            ]
        )
        self.set("_pos_attrs_json", attrs_json)

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
        # Try to get from object attribute first
        try:
            attrs = object.__getattribute__(self, "_pos_attrs_data")
            if attrs:
                return attrs
        except AttributeError:
            pass

        # Fall back to JSON deserialization
        import json

        attrs_json = self.get("_pos_attrs_json")
        if attrs_json:
            try:
                attrs_data = json.loads(attrs_json)
                return [
                    AttributeInfo(
                        name=a["name"],
                        value=a["value"],
                        start_line=a["start_line"],
                        start_col=a["start_col"],
                        end_line=a["end_line"],
                        end_col=a["end_col"],
                    )
                    for a in attrs_data
                ]
            except (json.JSONDecodeError, KeyError):
                pass

        return []


class LXMLPositionEnricher:
    """
    Custom lxml parser that enriches elements with position information.

    Usage:
        enricher = LXMLPositionEnricher(xml_content)
        root = enricher.root

        # Access position info:
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

        # Create custom parser with PositionElement class
        parser = etree.XMLParser()
        lookup = etree.ElementDefaultClassLookup(element=PositionElement)
        parser.set_element_class_lookup(lookup)

        # Parse with lxml
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

        # Group position elements by tag name
        pos_by_tag = {}
        for pos_elem in self.position_elements:
            if pos_elem.name not in pos_by_tag:
                pos_by_tag[pos_elem.name] = []
            pos_by_tag[pos_elem.name].append(pos_elem)

        # Group lxml elements by tag name
        lxml_by_tag = {}
        for lxml_elem in lxml_elements:
            tag = self._get_tag_name(lxml_elem)
            if tag:
                if tag not in lxml_by_tag:
                    lxml_by_tag[tag] = []
                lxml_by_tag[tag].append(lxml_elem)

        # Match and enrich elements with same tag name by order
        for tag_name in lxml_by_tag:
            if tag_name in pos_by_tag:
                lxml_list = lxml_by_tag[tag_name]
                pos_list = pos_by_tag[tag_name]

                for i in range(min(len(lxml_list), len(pos_list))):
                    lxml_elem = lxml_list[i]
                    pos_elem = pos_list[i]

                    if self._attributes_match(lxml_elem, pos_elem):
                        lxml_elem._set_position_data(
                            start_line=pos_elem.start_line,
                            start_col=pos_elem.start_col,
                            end_line=pos_elem.end_line,
                            end_col=pos_elem.end_col,
                            is_self_closing=pos_elem.is_self_closing,
                            position_attributes=pos_elem.attributes,
                        )

    def _traverse_lxml(self, element, elements_list):
        """Traverse lxml tree in document order."""
        if isinstance(element.tag, str):
            elements_list.append(element)

        for child in element:
            self._traverse_lxml(child, elements_list)

    def _get_tag_name(self, element) -> Optional[str]:
        """Get tag name from lxml element, handling namespaces."""
        tag = element.tag

        if not isinstance(tag, str):
            return None

        if "}" in tag:
            tag = tag.split("}")[1]
        return tag

    def _attributes_match(self, lxml_elem, pos_elem: ElementInfo) -> bool:
        """Check if attributes match between lxml element and position element."""
        lxml_attrs = dict(lxml_elem.attrib)
        pos_attrs = {attr.name: attr.value for attr in pos_elem.attributes}

        if not lxml_attrs and not pos_attrs:
            return True

        if len(lxml_attrs) != len(pos_attrs):
            return False

        for key, value in lxml_attrs.items():
            if key not in pos_attrs or pos_attrs[key] != value:
                return False

        return True


def demo():
    """Demonstration of the enriched lxml parser."""
    xml_test = b"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template name="Test Template 1" id="test_template_1">
        <li>text<strong
                t-out="o.name"
                t-options="{&quot;widget&quot;: &quot;float&quot;, &quot;precision&quot;: 2}"
            />
        </li>
    </template>
</odoo>"""

    print("=== XML Position Parser Demo ===\n")

    enricher = LXMLPositionEnricher(xml_test)
    root = enricher.root

    print("Testing <strong> element with multi-line attributes:\n")

    strong_elements = root.xpath("//strong")
    if strong_elements:
        strong = strong_elements[0]
        print(f"<{strong.tag}>")
        print(f"  lxml attributes: {dict(strong.attrib)}")
        print(f"  Position: ({strong.start_line},{strong.start_col}) → ({strong.end_line},{strong.end_col})")
        print(f"  Self-closing: {strong.is_self_closing}")

        if strong.position_attributes:
            print(f"\n  Parsed attributes with positions:")
            for attr in strong.position_attributes:
                print(f"    • {attr.name} = {repr(attr.value)}")
                print(f"      Position: ({attr.start_line},{attr.start_col}) → ({attr.end_line},{attr.end_col})")
        else:
            print(f"\n  ⚠️  WARNING: position_attributes is empty!")

    print("\n" + "=" * 70)
    print("\nAll elements:")
    for elem in root.iter():
        if isinstance(elem.tag, str):
            print(f"  <{elem.tag}> @ line {elem.start_line}, col {elem.start_col}")


if __name__ == "__main__":
    demo()
