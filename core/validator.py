from typing import List, Dict, Optional
import re
from .xliff_obj import TranslationUnit

class Validator:
    """
    Validates the translation output from AI.
    """
    
    def validate_structure(self, tu: TranslationUnit) -> List[str]:
        """
        Checks if the translated text contains all required placeholders.
        """
        errors = []
        source_placeholders = re.findall(r'\{\d+\}', tu.source_abstracted)
        target_placeholders = re.findall(r'\{\d+\}', tu.target_abstracted)
        
        # Check 1: Count mismatch
        if len(source_placeholders) != len(target_placeholders):
            # It's possible for some languages to drop tags but usually not safety tags.
            # For MVP, we enforce strict count.
            errors.append(f"Tag count mismatch: Source has {len(source_placeholders)}, Target has {len(target_placeholders)}")
            
        # Check 2: Hallucination (placeholder in target not in source)
        source_set = set(source_placeholders)
        for ph in target_placeholders:
            if ph not in source_set:
                errors.append(f"Found hallucinated tag {ph} in target.")
                
        # Check 3: Missing tags
        target_set = set(target_placeholders)
        for ph in source_placeholders:
            if ph not in target_set:
                errors.append(f"Missing tag {ph} in target.")
                
        return errors
