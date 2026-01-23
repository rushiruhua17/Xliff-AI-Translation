import re
from dataclasses import dataclass, field
from typing import List, Set, Dict, Any, Optional
from collections import Counter

@dataclass
class QAIssue:
    type: str  # 'missing', 'extra', 'invalid', 'empty'
    severity: str  # 'error', 'warning'
    message: str
    details: Any = None

@dataclass
class QAResult:
    status: str  # 'ok', 'warning', 'error'
    issues: List[QAIssue] = field(default_factory=list)
    tag_stats: str = ""
    qa_details: Dict[str, Any] = field(default_factory=dict)

class QAChecker:
    def __init__(self):
        # Pattern for valid tokens {0}, {1}, etc.
        self.valid_token_pattern = re.compile(r"\{\d+\}")
        # Pattern for invalid tokens (malformed)
        self.invalid_token_pattern = re.compile(r"\{(?!\d+\})")  # { followed by non-digit or missing }

    def check_unit(self, source_text: str, target_text: str, unit_state: str) -> QAResult:
        source_text = source_text or ""
        target_text = target_text or ""
        
        qa_details = {}
        issues = []
        
        # Extract tokens from source and target
        source_counts = Counter(self.valid_token_pattern.findall(source_text))
        target_counts = Counter(self.valid_token_pattern.findall(target_text))
        
        # A. Token Count Matching (Core Check)
        missing_tokens = []
        extra_tokens = []
        
        # Check for missing or under-counted tokens
        for token, count in source_counts.items():
            if target_counts[token] < count:
                missing_tokens.extend([token] * (count - target_counts[token]))
        
        # Check for extra or over-counted tokens
        for token, count in target_counts.items():
            if source_counts[token] < count:
                extra_tokens.extend([token] * (count - source_counts[token]))
        
        # B. Invalid Token Detection
        invalid_matches = self.invalid_token_pattern.findall(target_text)
        
        # Update tag_stats
        source_tag_count = sum(source_counts.values())
        target_tag_count = sum(target_counts.values())
        tag_stats = f"TAG: {target_tag_count}/{source_tag_count}"
        
        # C. QA Logic
        has_errors = False
        
        if missing_tokens:
            sorted_missing = sorted(missing_tokens)
            qa_details["missing"] = sorted_missing
            issues.append(QAIssue(
                type="missing", 
                severity="error", 
                message=f"Missing/Duplicate tokens: {', '.join(sorted_missing)}",
                details=sorted_missing
            ))
            has_errors = True
            
        if extra_tokens:
            sorted_extra = sorted(extra_tokens)
            qa_details["extra"] = sorted_extra
            issues.append(QAIssue(
                type="extra", 
                severity="error", 
                message=f"Extra tokens: {', '.join(sorted_extra)}",
                details=sorted_extra
            ))
            has_errors = True
            
        if invalid_matches:
            qa_details["invalid"] = invalid_matches
            issues.append(QAIssue(
                type="invalid", 
                severity="error", 
                message=f"Invalid token format: {', '.join(invalid_matches[:3])}",
                details=invalid_matches
            ))
            has_errors = True
        
        status = "ok"
        if has_errors:
            status = "error"
        elif not target_text and unit_state in ["translated", "edited"]:
            issues.append(QAIssue(
                type="empty",
                severity="warning",
                message="Empty translation"
            ))
            status = "warning"
        else:
            status = "ok"
            
        return QAResult(status=status, issues=issues, tag_stats=tag_stats, qa_details=qa_details)
