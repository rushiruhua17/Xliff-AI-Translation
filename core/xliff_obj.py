from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class TranslationUnit:
    """
    Represents a single translation unit (trans-unit) from an XLIFF file.
    """
    id: str
    source_raw: str  # Original XML string of <source>
    target_raw: str = "" # Original XML string of <target>
    
    source_abstracted: str = "" # Text with {n} placeholders
    target_abstracted: str = "" # Text with {n} placeholders
    
    # Map from placeholder ID (str "1") to original XML tag content (str "<bpt id='1'>...</bpt>")
    tags_map: Dict[str, str] = field(default_factory=dict)
    
    state: str = "new" # XLIFF state attribute
    errors: List[str] = field(default_factory=list)
    
    # New fields for V2.1+
    tag_stats: str = "" # e.g. "TAG: 2/2"
    qa_status: str = "ok" # ok, warning, error
    qa_details: Dict[str, List[str]] = field(default_factory=dict) # {"missing": ["{0}"], "extra": ["{99}"]}
    
    def to_dict(self):
        return {
            "id": self.id,
            "source_raw": self.source_raw,
            "source_abstracted": self.source_abstracted,
            "target_abstracted": self.target_abstracted,
            "state": self.state
        }
