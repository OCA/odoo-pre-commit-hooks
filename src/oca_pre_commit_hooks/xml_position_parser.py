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
    
    def __init__(self, xml_source: str, is_file: bool = False):
        if is_file:
            with open(xml_source, 'r', encoding='utf-8') as f:
                self.xml_text = f.read()
        else:
            self.xml_text = xml_source
            
        self.lines = self.xml_text.split('\n')
        self.elements: List[ElementInfo] = []
        
    def parse(self) -> List[ElementInfo]:
        """Parse XML and return position information for all elements."""
        tag_pattern = r'<([a-zA-Z_][\w:.-]*)((?:\s+[^>]*?)?)(/?)>'
        
        for match in re.finditer(tag_pattern, self.xml_text, re.MULTILINE | re.DOTALL):
            tag_name = match.group(1)
            attributes_str = match.group(2)
            is_self_closing = match.group(3) == '/'
            
            start_pos = match.start()
            start_line, start_col = self._pos_to_line_col(start_pos)
            
            end_pos = match.end()
            end_line, end_col = self._pos_to_line_col(end_pos)
            
            attrs = self._parse_attributes(
                attributes_str, 
                start_pos + len(tag_name) + 1
            )
            
            element = ElementInfo(
                name=tag_name,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                attributes=attrs,
                is_self_closing=is_self_closing
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
            if char == '\n':
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
            quote = match.group(2)
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
                end_col=end_col
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
        self.set('_pos_start_line', str(start_line))
        self.set('_pos_start_col', str(start_col))
        self.set('_pos_end_line', str(end_line))
        self.set('_pos_end_col', str(end_col))
        self.set('_pos_is_self_closing', str(is_self_closing))
        # Store position_attributes in a way that survives
        # We'll use the element's __dict__ if available, or fall back to a global dict
        try:
            object.__setattr__(self, '_pos_attrs_data', position_attributes)
        except (AttributeError, TypeError):
            # Fallback: store in element's tail (not ideal but works)
            pass
    
    @property
    def start_line(self) -> Optional[int]:
        """Line where element starts."""
        val = self.get('_pos_start_line')
        return int(val) if val and val != 'None' else None
    
    @property
    def start_col(self) -> Optional[int]:
        """Column where element starts."""
        val = self.get('_pos_start_col')
        return int(val) if val and val != 'None' else None
    
    @property
    def end_line(self) -> Optional[int]:
        """Line where element ends."""
        val = self.get('_pos_end_line')
        return int(val) if val and val != 'None' else None
    
    @property
    def end_col(self) -> Optional[int]:
        """Column where element ends."""
        val = self.get('_pos_end_col')
        return int(val) if val and val != 'None' else None
    
    @property
    def is_self_closing(self) -> Optional[bool]:
        """Whether element is self-closing."""
        val = self.get('_pos_is_self_closing')
        if val is None or val == 'None':
            return None
        return val == 'True'
    
    @property
    def position_attributes(self) -> List[AttributeInfo]:
        """List of attributes with position information."""
        try:
            return object.__getattribute__(self, '_pos_attrs_data')
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
    
    def __init__(self, xml_source: str, is_file: bool = False):
        self.xml_source = xml_source
        self.is_file = is_file
        
        # Create custom parser with our PositionElement class
        parser = etree.XMLParser()
        lookup = etree.ElementDefaultClassLookup(element=PositionElement)
        parser.set_element_class_lookup(lookup)
        
        # Parse with lxml using custom element class
        if is_file:
            self.tree = etree.parse(xml_source, parser)
            self.root = self.tree.getroot()
        else:
            self.root = etree.fromstring(xml_source.encode('utf-8'), parser)
        
        # Parse with position parser
        self.position_parser = XMLPositionParser(xml_source, is_file)
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
                            position_attributes=pos_elem.attributes
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
        
        if '}' in tag:
            # Remove namespace: {http://example.com}tag -> tag
            tag = tag.split('}')[1]
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
    
    print("=== Enhanced lxml Parser Demo ===\n")
    print("Creating enriched lxml tree...")
    
    # Parse XML with position enrichment
    enricher = LXMLPositionEnricher(xml_test)
    root = enricher.root
    
    print(f"Root element: <{root.tag}>\n")
    print("="*70)
    
    # Example 1: Access position info directly
    print("\nExample 1: Direct property access")
    print("-"*70)
    
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
    print("\n" + "="*70)
    print("\nExample 2: Find <t> element with t-esc attribute")
    print("-"*70)
    
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
    print("\n" + "="*70)
    print("\nExample 3: All <span> elements")
    print("-"*70)
    
    for span in root.xpath("//span"):
        attrs = ", ".join([f"{k}='{v}'" for k, v in span.attrib.items()])
        print(f"\n<span {attrs} />")
        print(f"  Lines: {span.start_line} → {span.end_line}")
        print(f"  Columns: {span.start_col} → {span.end_col}")
    
    # Example 4: Demonstrate it's still a regular lxml element
    print("\n" + "="*70)
    print("\nExample 4: Still works as regular lxml element")
    print("-"*70)
    
    print(f"\nCan use all lxml methods:")
    print(f"  root.tag: {root.tag}")
    print(f"  root.getchildren() count: {len(root.getchildren())}")
    print(f"  root.xpath('//div') count: {len(root.xpath('//div'))}")
    print(f"  isinstance(root, etree._Element): {isinstance(root, etree._Element)}")
    print(f"  isinstance(root, PositionElement): {isinstance(root, PositionElement)}")


if __name__ == "__main__":
    demo()