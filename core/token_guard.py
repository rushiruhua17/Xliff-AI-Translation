import re
from collections import Counter
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    valid: bool
    missing: List[str]
    extra: List[str]
    order_errors: List[str]
    pairing_errors: List[str]
    message: str

class TokenGuard:
    """
    Strict validation for XLIFF inline tokens in AI-generated translations.
    Enforces:
    1. Multi-set integrity (Count + Duplicates).
    2. Pairing integrity (<bpt> must precede <ept>).
    """
    
    TOKEN_REGEX = re.compile(r'\{\d+\}')
    
    @staticmethod
    def extract_tokens(text: str) -> List[str]:
        return TokenGuard.TOKEN_REGEX.findall(text)

    @staticmethod
    def validate(source_text: str, target_text: str, tags_map: Dict[str, str]) -> ValidationResult:
        source_tokens = TokenGuard.extract_tokens(source_text)
        target_tokens = TokenGuard.extract_tokens(target_text)
        
        missing = []
        extra = []
        order_errors = []
        pairing_errors = []
        
        # 1. Multi-set Check (Counts)
        src_counts = Counter(source_tokens)
        tgt_counts = Counter(target_tokens)
        
        # Check missing
        for token, count in src_counts.items():
            if tgt_counts[token] < count:
                missing.extend([token] * (count - tgt_counts[token]))
                
        # Check extra
        for token, count in tgt_counts.items():
            if tgt_counts[token] > src_counts[token]:
                extra.extend([token] * (tgt_counts[token] - src_counts[token]))
                
        # 2. Pairing Check (<bpt>...<ept>)
        # We need to analyze tags_map to find pairs
        # Map: "1" -> "<bpt id='1'>...</bpt>"
        # Wait, Abstractor returns full tag content.
        # We need to parse the XML inside tags_map values to know type and ID.
        
        # Build ID map: {'rid_1': {'bpt': '{1}', 'ept': '{2}'}}
        # rid = real id (from xliff attribute)
        pairs_map = {} 
        
        for placeholder_id, tag_content in tags_map.items():
            token = f"{{{placeholder_id}}}"
            
            # Simple regex to detect type and id
            # <bpt id="1">
            bpt_match = re.search(r'<bpt[^>]*id=["\']([^"\']+)["\']', tag_content)
            ept_match = re.search(r'<ept[^>]*id=["\']([^"\']+)["\']', tag_content)
            
            if bpt_match:
                rid = bpt_match.group(1)
                if rid not in pairs_map: pairs_map[rid] = {}
                pairs_map[rid]['bpt'] = token
                
            elif ept_match:
                rid = ept_match.group(1)
                if rid not in pairs_map: pairs_map[rid] = {}
                pairs_map[rid]['ept'] = token

        # Check pairs in Target
        for rid, tokens in pairs_map.items():
            bpt = tokens.get('bpt')
            ept = tokens.get('ept')
            
            if bpt and ept and bpt in target_tokens and ept in target_tokens:
                # Find indices
                # Note: There could be duplicates, but XLIFF IDs should be unique within a unit ideally.
                # If duplicates exist, it gets complex. Assuming unique IDs for now.
                try:
                    bpt_idx = target_tokens.index(bpt)
                    ept_idx = target_tokens.index(ept)
                    
                    if bpt_idx > ept_idx:
                        pairing_errors.append(f"Broken Pair: {bpt} appears after {ept}")
                except ValueError:
                    pass # Handled by missing check

        valid = not (missing or extra or pairing_errors)
        
        msg_parts = []
        if missing: msg_parts.append(f"Missing: {', '.join(missing)}")
        if extra: msg_parts.append(f"Extra: {', '.join(extra)}")
        if pairing_errors: msg_parts.append(f"Pairing: {', '.join(pairing_errors)}")
        
        return ValidationResult(
            valid=valid,
            missing=missing,
            extra=extra,
            order_errors=[], # Not enforcing strict global order for now
            pairing_errors=pairing_errors,
            message=" | ".join(msg_parts) if msg_parts else "Valid"
        )
