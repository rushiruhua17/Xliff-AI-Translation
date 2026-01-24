import json
from typing import List, Dict, Any, Optional
from core.profile import TranslationProfile, ProjectMetadata, TranslationBrief

class PromptBuilder:
    """
    Constructs structured system and user prompts based on TranslationProfile.
    """
    
    @staticmethod
    def build_system_message(profile: Optional[TranslationProfile], src_lang: str, tgt_lang: str) -> str:
        """
        Builds the system instruction strictly adhering to Phase 5 documentation.
        """
        role = "You are a professional translator."
        
        # Base task
        task = f"Translate the following XLIFF segments from {src_lang} to {tgt_lang}."
        
        # Constraints from Profile
        constraints = []
        
        if profile:
            # 1. Style & Tone
            brief = profile.brief
            if brief.tone and brief.tone != "neutral":
                constraints.append(f"Tone: {brief.tone}")
            if brief.formality and brief.formality != "neutral":
                constraints.append(f"Formality: {brief.formality}")
            if brief.locale_variant:
                constraints.append(f"Locale Variant: {brief.locale_variant}")
            
            # 2. Audience (Moved from Metadata)
            if brief.target_audience:
                constraints.append(f"Target Audience: {brief.target_audience}")
                
            # 3. Formatting & Terminology (Strict)
            if brief.formatting.preserve_placeholders:
                constraints.append("SAFETY: Preserve all {n} placeholders exactly as they appear in the source. Do not move or translate them.")
            
            # Formatting Rules (Background Phase 5)
            fmt = brief.formatting
            if fmt.preserve_source_numbers:
                constraints.append("Numbers: Preserve all source numbers exactly as written.")
            if fmt.unit_system:
                unit_instr = f"Units: Use {fmt.unit_system} system."
                if fmt.dual_units:
                    unit_instr += " Provide dual units (e.g. SI + Imperial) if applicable."
                constraints.append(unit_instr)
            if fmt.quotes_style:
                constraints.append(f"Typography: Use {fmt.quotes_style} quotes.")
            if not fmt.keep_source_capitalization:
                constraints.append("Capitalization: Adjust capitalization to match target language conventions.")

            if brief.style_guide_notes:
                constraints.append(f"Style Guide: {brief.style_guide_notes}")
                
            # Terminology Policy (Background Phase 5)
            term = brief.terminology
            constraints.append(f"Terminology Strictness: {term.strictness}")
            if term.allow_explanation:
                constraints.append("Terminology: If a technical term is ambiguous, provide a brief explanation in brackets after the first occurrence.")
            if term.use_termbase:
                constraints.append("Terminology: Use standard industry terminology consistent with the domain.")
            
            # Do Not Translate / Forbidden (Phase 4)
            if term.do_not_translate:
                dnt_list = ", ".join(f'"{t}"' for t in term.do_not_translate)
                constraints.append(f"DO NOT TRANSLATE (Keep Original): {dnt_list}")
                
            if term.forbidden_terms:
                forbid_list = ", ".join(f'"{t}"' for t in term.forbidden_terms)
                constraints.append(f"FORBIDDEN TERMS (Do Not Use): {forbid_list}")

        else:
            # Legacy Fallback
            constraints.append("Preserve all placeholders and HTML tags.")

        # Output Format (Strict JSON)
        json_instruction = (
            "OUTPUT FORMAT:\n"
            "You must output strictly valid JSON. "
            "The root object must contain a key 'translations', which is a list of objects.\n"
            "Each object must have:\n"
            "  - 'id': (string, same as source)\n"
            "  - 'translation': (string, the target text)\n"
            "Do not include markdown formatting (```json). Return raw JSON only."
        )
        
        # Assemble
        prompt_parts = [role, task]
        if constraints:
            prompt_parts.append("\nCONSTRAINTS:")
            prompt_parts.extend([f"- {c}" for c in constraints])
        
        prompt_parts.append("\n" + json_instruction)
        
        return "\n".join(prompt_parts)

    @staticmethod
    def build_user_message(segments: List[Dict[str, str]]) -> str:
        """
        Formats the source segments into a clean JSON structure for the LLM.
        Expected segments format: [{'id': '1', 'source': 'text'}, ...]
        """
        # Minimal payload to save tokens and reduce noise
        clean_payload = [
            {"id": seg["id"], "source": seg["source"]} 
            for seg in segments
        ]
        return json.dumps(clean_payload, ensure_ascii=False, indent=2)
