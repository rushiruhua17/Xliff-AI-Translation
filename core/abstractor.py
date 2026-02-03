import re
from typing import Tuple, Dict
from dataclasses import dataclass
from lxml import etree
from core.xliff_inline_tags import INLINE_TAG_LOCALNAMES, INLINE_TAG_REGEX

@dataclass
class AbstractionResult:
    abstracted_text: str
    tags_map: Dict[str, str]

class TagAbstractor:
    """
    Handles the conversion between raw XLIFF XML content and AI-friendly text with placeholders.
    """
    
    # Regex to capture XLIFF inline tags: bpt, ept, ph, it, mrk, g, x, bx, ex
    # We want to capture the whole tag as one unit.
    # Note: This regex assumes tags are not nested inside attributes of other tags (which is true for valid XML)
    TAG_PATTERN = INLINE_TAG_REGEX

    def abstract(self, raw_xml: str) -> AbstractionResult:
        """
        Replaces tags with {1}, {2}, etc.
        """
        if not raw_xml:
            return AbstractionResult("", {})

        def strip_xmlns(s: str) -> str:
            return re.sub(r'\s+xmlns(:\w+)?="[^"]+"', '', s or "")

        allowed = set(INLINE_TAG_LOCALNAMES)
        try:
            parser = etree.XMLParser(recover=False, remove_blank_text=False)
            dummy_xml = f"<dummy>{raw_xml}</dummy>"
            dummy_root = etree.fromstring(dummy_xml.encode("utf-8"), parser)

            tags_map: Dict[str, str] = {}
            out = []
            if dummy_root.text:
                out.append(dummy_root.text)

            counter = 1
            for node in dummy_root:
                if isinstance(node.tag, str):
                    local = etree.QName(node).localname
                    if local in allowed:
                        placeholder = f"{{{counter}}}"
                        tag_content = strip_xmlns(etree.tostring(node, encoding="unicode", with_tail=False))
                        tags_map[str(counter)] = tag_content
                        out.append(placeholder)
                        counter += 1
                        if node.tail:
                            out.append(node.tail)
                        continue

                out.append(strip_xmlns(etree.tostring(node, encoding="unicode", with_tail=True)))

            abstracted_text = "".join(out)
            return AbstractionResult(abstracted_text, tags_map)
        except Exception:
            tags_map = {}
            counter = 1

            def replace_match(match):
                nonlocal counter
                tag_content = match.group(0)
                placeholder = f"{{{counter}}}"
                tags_map[str(counter)] = tag_content
                counter += 1
                return placeholder

            abstracted_text = self.TAG_PATTERN.sub(replace_match, raw_xml)
            return AbstractionResult(abstracted_text, tags_map)

    def reconstruct(self, abstracted_text: str, tags_map: Dict[str, str]) -> str:
        """
        Replaces {n} placeholders back with their original tags.
        """
        # Validate logic could go here (check if all keys in tags_map are used)
        
        result = abstracted_text
        # We iterate over keys to ensure we replace {1} before {10} if we did simple string replace,
        # but regex is safer to avoid replacing inner parts of other things if text contains {n} naturally?
        # For MVP, simple replacement is okay, but let's be slightly robust.
        # We can use a regex to find all {n} patterns and replace them if they exist in map.
        
        def replace_back(match):
            key = match.group(1)
            if key in tags_map:
                return tags_map[key]
            return match.group(0) # Keep as is if not found (or treat as literal text)

        # Pattern for {n} where n is digits
        result = re.sub(r'\{(\d+)\}', replace_back, result)
        
        return result
