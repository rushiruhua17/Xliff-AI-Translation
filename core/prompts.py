"""
Centralized prompt definitions for AI tasks.
Includes: Translation, Refinement, Tag Repair, Profile Generation.
"""

class SystemPrompts:
    # 1. Translation System Prompt
    # Used in core/prompt_builder.py
    TRANSLATION_BASE = "You are a professional translator."
    TRANSLATION_TASK = "Translate the following XLIFF segments from {src_lang} to {tgt_lang}."
    
    TRANSLATION_JSON_FORMAT = (
        "OUTPUT FORMAT:\n"
        "You must output strictly valid JSON. "
        "The root object must contain a key 'translations', which is a list of objects.\n"
        "Each object must have:\n"
        "  - 'id': (string, same as source)\n"
        "  - 'translation': (string, the target text)\n"
        "Do not include markdown formatting (```json). Return raw JSON only."
    )

    # 2. Repair System Prompt
    # Used in core/repair.py (to be implemented/updated)
    REPAIR_SYSTEM = (
        "You are a technical editor. "
        "Your task is to fix tag errors in the translation while preserving meaning.\n"
        "Ensure ALL required tokens (e.g. {0}, {1}) from source appear in the target."
    )
    
    REPAIR_USER_TEMPLATE = (
        "Source: {source}\n"
        "Broken Target: {target}\n"
        "Required Tokens: {tokens}\n\n"
        "Fix the target to include all tokens naturally. Output ONLY the fixed target string."
    )

    # 3. Refinement System Prompt
    # Used in Workbench / RefineWorker
    REFINE_SYSTEM = (
        "You are a professional translator and editor. "
        "Your task is to refine the translation based on user instructions.\n"
        "CRITICAL: You must preserve all XLIFF tokens exactly as they appear in the source.\n"
        "Output ONLY the refined translation text."
    )
    
    REFINE_USER_TEMPLATE = (
        "Source: {source}\n"
        "Current Translation: {target}\n"
        "User Instruction: {instruction}\n\n"
        "Refined Translation:"
    )

    # 4. Profile Generation Prompt
    # Used in ProfileGeneratorWorker
    PROFILE_GEN_SYSTEM = "You are a localization expert. Output ONLY valid JSON."
    
    PROFILE_GEN_USER = (
        "Analyze the following text sample and suggest a comprehensive translation brief.\n"
        "Return strictly valid JSON matching this schema version 1.0:\n"
        "{\n"
        "  \"target_audience\": \"e.g. Expert Developers, End Users\",\n"
        "  \"tone\": \"neutral|formal|casual|friendly|authoritative\",\n"
        "  \"formality\": \"neutral|formal|informal\",\n"
        "  \"terminology_strictness\": \"strict|prefer|loose\",\n"
        "  \"unit_system\": \"SI|Imperial|Mixed\",\n"
        "  \"do_not_translate\": [\"list\", \"of\", \"terms\"],\n"
        "  \"style_guide_notes\": \"Summary of style and tone constraints\"\n"
        "}\n"
        "Do NOT guess client names or specific project types (e.g. 'Apple Manual'). Focus on style and linguistic properties.\n\n"
        "Sample Text:\n{text}"
    )
