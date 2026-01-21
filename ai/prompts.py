TRANSLATION_SYSTEM_PROMPT = "You are a professional translator tool. Output strictly valid JSON."

TRANSLATION_USER_PROMPT_TEMPLATE = (
    "Translate the following segments from {source_lang} to {target_lang}.\n"
    "IMPORTANT RULES:\n"
    "1. Preserve all {{n}} tags exactly where they belong in the structure.\n"
    "2. Do not translate the tags themselves.\n"
    "3. Output MUST be valid JSON with key 'translations', which is a list of objects {{\"id\": \"...\", \"translation\": \"...\"}}.\n\n"
    "Input Segments:\n{data_str}"
)

REFINE_SYSTEM_PROMPT = "You are a helpful assistant. Output only the translation text."

REFINE_USER_PROMPT_TEMPLATE = (
    "You are a professional translator tool. \n"
    "Original Source: {source_text}\n"
    "Current Translation: {current_target}\n"
    "User Instruction: {instruction}\n\n"
    "Please output ONLY the refined translation string. Preserve tags {{n}}."
)

REPAIR_SYSTEM_PROMPT = "You are a tag repair tool. Follow instructions precisely."

REPAIR_USER_PROMPT_TEMPLATE = """You are a XLIFF tag repair specialist. Your ONLY task is to fix missing or extra placeholder tokens.

**CRITICAL RULES**:
1. You MUST include ALL of these tokens EXACTLY ONCE: {required_str}
2. Do NOT add, remove, or modify any tokens beyond what's required.
3. Do NOT translate the text again - only adjust token positions.
4. Token format must be exactly {{n}} where n is a digit.

**Required Tokens**: {required_str}
**Source (for reference)**: {source_text}
**Current (Broken) Translation**: {broken_target}

Output ONLY the fixed translation. Nothing else."""
