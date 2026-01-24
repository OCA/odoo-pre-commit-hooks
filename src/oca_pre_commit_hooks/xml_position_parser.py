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
    start_index: int  # Nuevo: índice de inicio en la cadena
    end_index: int    # Nuevo: índice de fin en la cadena

@dataclass
class ElementInfo:
    """Position information for an XML element."""
    name: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    start_index: int  # Nuevo: índice de inicio en la cadena
    end_index: int    # Nuevo: índice de fin en la cadena
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
        self.xml_text = xml_content.decode('utf-8')
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
                start_index=start_pos,  # Guardamos el índice absoluto
                end_index=end_pos,      # Guardamos el índice absoluto
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
                end_col=end_col,
                start_index=attr_start_pos,  # Guardamos el índice absoluto
                end_index=attr_end_pos       # Guardamos el índice absoluto
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
        - start_index: Character index where element starts
        - end_index: Character index where element ends
        - is_self_closing: Whether element is self-closing
        - position_attributes: List of AttributeInfo objects
    """
    
    __slots__ = ()
    
    def _set_position_data(self, start_line, start_col, end_line, end_col, 
                          start_index, end_index, is_self_closing, position_attributes):
        """Internal method to set position data."""
        self.set('_pos_start_line', str(start_line))
        self.set('_pos_start_col', str(start_col))
        self.set('_pos_end_line', str(end_line))
        self.set('_pos_end_col', str(end_col))
        self.set('_pos_start_index', str(start_index))  # Nuevo
        self.set('_pos_end_index', str(end_index))      # Nuevo
        self.set('_pos_is_self_closing', str(is_self_closing))
        try:
            object.__setattr__(self, '_pos_attrs_data', position_attributes)
        except (AttributeError, TypeError):
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
    def start_index(self) -> Optional[int]:
        """Character index where element starts."""
        val = self.get('_pos_start_index')
        return int(val) if val and val != 'None' else None
    
    @property
    def end_index(self) -> Optional[int]:
        """Character index where element ends."""
        val = self.get('_pos_end_index')
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
        print(element.start_index)
        
        # Extract the exact text:
        xml_text = xml_content.decode('utf-8')
        element_text = xml_text[element.start_index:element.end_index]
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
        lxml_elements = []
        self._traverse_lxml(self.root, lxml_elements)
        
        print(f"DEBUG: Found {len(lxml_elements)} lxml elements")
        print(f"DEBUG: Found {len(self.position_elements)} position elements")
        
        pos_by_tag = {}
        for pos_elem in self.position_elements:
            if pos_elem.name not in pos_by_tag:
                pos_by_tag[pos_elem.name] = []
            pos_by_tag[pos_elem.name].append(pos_elem)
        
        print(f"DEBUG: Position elements by tag: {list(pos_by_tag.keys())}")
        
        lxml_by_tag = {}
        for lxml_elem in lxml_elements:
            tag = self._get_tag_name(lxml_elem)
            if tag:
                if tag not in lxml_by_tag:
                    lxml_by_tag[tag] = []
                lxml_by_tag[tag].append(lxml_elem)
        
        print(f"DEBUG: lxml elements by tag: {list(lxml_by_tag.keys())}")
        
        for tag_name in lxml_by_tag:
            if tag_name in pos_by_tag:
                lxml_list = lxml_by_tag[tag_name]
                pos_list = pos_by_tag[tag_name]
                
                print(f"DEBUG: Matching {len(lxml_list)} lxml <{tag_name}> with {len(pos_list)} position <{tag_name}>")
                
                for i in range(min(len(lxml_list), len(pos_list))):
                    lxml_elem = lxml_list[i]
                    pos_elem = pos_list[i]
                    
                    lxml_attrs = dict(lxml_elem.attrib)
                    pos_attrs = {attr.name: attr.value for attr in pos_elem.attributes}
                    print(f"  DEBUG: Comparing element {i}:")
                    print(f"    lxml attrs: {lxml_attrs}")
                    print(f"    pos attrs: {pos_attrs}")
                    
                    if self._attributes_match(lxml_elem, pos_elem):
                        print(f"    ✓ MATCH! Setting position data")
                        lxml_elem._set_position_data(
                            start_line=pos_elem.start_line,
                            start_col=pos_elem.start_col,
                            end_line=pos_elem.end_line,
                            end_col=pos_elem.end_col,
                            start_index=pos_elem.start_index,  # Nuevo
                            end_index=pos_elem.end_index,      # Nuevo
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
        
        if not isinstance(tag, str):
            return None
        
        if '}' in tag:
            tag = tag.split('}')[1]
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
    
    enricher = LXMLPositionEnricher(xml_test)
    root = enricher.root
    xml_text = xml_test.decode('utf-8')
    
    print(f"Root element: <{root.tag}>\n")
    print("="*70)
    
    # Ejemplo con índices de caracteres
    print("\nExample: Extract exact text using character indices")
    print("-"*70)
    
    templates = root.xpath("//template")
    for template in templates:
        print(f"\n<{template.tag} id='{template.get('id')}'>")
        print(f"  start_index: {template.start_index}")
        print(f"  end_index: {template.end_index}")
        print(f"  start_line: {template.start_line}, start_col: {template.start_col}")
        print(f"  end_line: {template.end_line}, end_col: {template.end_col}")
        
        # ¡Aquí está la magia! Extrae el texto exacto
        if template.start_index is not None and template.end_index is not None:
            exact_text = xml_text[template.start_index:template.end_index]
            print(f"\n  Exact text from xml_content[{template.start_index}:{template.end_index}]:")
            print(f"  '{exact_text}'")
    
    # Ejemplo con atributos
    print("\n" + "="*70)
    print("\nExample: Extract attribute text using indices")
    print("-"*70)
    
    for template in templates:
        if template.position_attributes:
            print(f"\n<{template.tag}>")
            for attr in template.position_attributes:
                print(f"  Attribute: {attr.name}='{attr.value}'")
                print(f"    indices: [{attr.start_index}:{attr.end_index}]")
                if attr.start_index is not None and attr.end_index is not None:
                    attr_text = xml_text[attr.start_index:attr.end_index]
                    print(f"    exact text: '{attr_text}'")
    
    # Ejemplo con span
    print("\n" + "="*70)
    print("\nExample: All <span> elements with exact text")
    print("-"*70)
    
    for span in root.xpath("//span"):
        print(f"\nElement: <span>")
        print(f"  Indices: [{span.start_index}:{span.end_index}]")
        if span.start_index is not None and span.end_index is not None:
            span_text = xml_text[span.start_index:span.end_index]
            print(f"  Exact text: '{span_text}'")


if __name__ == "__main__":
    demo()