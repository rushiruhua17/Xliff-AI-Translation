from lxml import etree
from typing import List, Optional
import os
from .xliff_obj import TranslationUnit
from .logger import get_logger

logger = get_logger(__name__)

class XliffParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'} # Default to 1.2
        self.tree = None
        self.root = None

    def load(self):
        """Parses the XLIFF file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        parser = etree.XMLParser(remove_blank_text=False)
        self.tree = etree.parse(self.file_path, parser)
        self.root = self.tree.getroot()
        
        # Detect namespace if strictly 1.2 or 2.0, for now assumes 1.2 structure mainly
        # MemoQ usually uses 1.2
        if self.root.nsmap:
            # Update default namespace if one exists without prefix
            if None in self.root.nsmap:
                self.ns['xliff'] = self.root.nsmap[None]

    def get_translation_units(self) -> List[TranslationUnit]:
        """Extracts translation units from the parsed tree."""
        units = []
        # Find all trans-unit elements. XLIFF 1.2 structure: <file><body><trans-unit>
        # Handling namespaces can be tricky, trying generic local-name check or namespaced
        
        # XPath to find trans-unit regardless of depth, though usually under body
        trans_units = self.root.xpath('//*[local-name()="trans-unit"]')
        
        for tu in trans_units:
            tu_id = tu.get('id')
            
            source_nodes = tu.xpath('*[local-name()="source"]')
            target_nodes = tu.xpath('*[local-name()="target"]')
            
            source_node = source_nodes[0] if source_nodes else None
            target_node = target_nodes[0] if target_nodes else None
            
            # Extract raw XML content of source/target
            # using encoding logic to keep inner tags
            source_raw = self._node_to_string(source_node) if source_node is not None else ""
            target_raw = self._node_to_string(target_node) if target_node is not None else ""
            
            state = target_node.get('state') if target_node is not None else "new"

            units.append(TranslationUnit(
                id=tu_id,
                source_raw=source_raw,
                target_raw=target_raw,
                state=state
            ))
            
        return units

    def update_targets(self, units: List[TranslationUnit], output_path: str = None):
        """Updates the DOM with new target content and saves to file."""
        trans_units_map = {u.id: u for u in units}
        
        xml_trans_units = self.root.xpath('//*[local-name()="trans-unit"]')
        
        for xml_tu in xml_trans_units:
            tu_id = xml_tu.get('id')
            if tu_id in trans_units_map:
                update_data = trans_units_map[tu_id]
                
                # If we have a new target raw content (reconstructed), string update it
                # Note: This is a simplifiction. Ideally we construct lxml nodes.
                # But for MVP, parsing the raw string back to nodes is easier if structure is valid.
                
                if update_data.target_raw:
                    target_nodes = xml_tu.xpath('*[local-name()="target"]')
                    if not target_nodes:
                        # Create target node if missing
                        target_node = etree.SubElement(xml_tu, f"{{{self.ns['xliff']}}}target")
                    else:
                        target_node = target_nodes[0]
                    
                    # Clear current content
                    target_node.text = None
                    for child in list(target_node):
                        target_node.remove(child)
                        
                    # Repopulate from raw XML string
                    # Wrap in a dummy root to parse content with mixed text/tags
                    try:
                        dummy_xml = f"<dummy>{update_data.target_raw}</dummy>"
                        dummy_root = etree.fromstring(dummy_xml)
                        
                        # Copy text/children to target_node
                        target_node.text = dummy_root.text
                        for child in dummy_root:
                            target_node.append(child)
                            
                        # Update state
                        if update_data.state:
                            target_node.set('state', "translated") # Force translated state for now or use valid state
                            
                    except etree.XMLSyntaxError as e:
                        logger.warning(f"XML reconstruction failed for TU {tu_id}: {e}")
                        # Fallback: text only
                        target_node.text = update_data.target_abstracted

        save_path = output_path if output_path else self.file_path
        self.tree.write(save_path, encoding="utf-8", xml_declaration=True)

    def _node_to_string(self, node) -> str:
        """Converts an lxml node's *children* to a string (inner XML)."""
        if node is None:
            return ""
        # tounicode with method='xml' includes the tag itself.
        # We need inner content.
        # Simple hack: tounicode(node) then strip outer tags? 
        # Or better: iterate text and children.
        
        parts = []
        if node.text:
            parts.append(node.text)
        for child in node:
            child_str = etree.tostring(child, encoding='unicode')
            # Post-processing to remove specific namespace declaration if it clutters inner tags
            # This is a bit hacky but needed to keep tags clean for abstractor regex matching
            # and to look like original source.
            child_str = child_str.replace(' xmlns="urn:oasis:names:tc:xliff:document:1.2"', '')
            parts.append(child_str)
        return "".join(parts)
