# Phase 5 Refined: Robust Profile Injection & Verification

I will implement the `PromptBuilder` with strict constraints, batch support, and robust validation as requested.

## 1. Core: `core/prompt_builder.py`
I will implement `PromptBuilder` to handle batch segments and profile injection.
- **Input**: `segments` (list of dicts `{id, text}`), `profile` (optional), `src_lang`, `tgt_lang`.
- **Logic**:
    - **System Message**:
        - **Role**: "Professional Translator".
        - **Constraints**: 
            - **Style**: Map `tone`, `formality`, `audience` to bullet points.
            - **Locale**: `locale_variant`.
            - **Formatting**: `formatting_rules`.
            - **Terminology**: `strictness` level.
            - **Safety**: "Preserve all {n} placeholders exactly."
        - **Output Format**: Strict JSON schema instruction.
    - **User Message**: 
        - Source text block formatted as JSON list for clarity (e.g., `[{"id": "1", "source": "..."}]`).
- **Optimization**: Minimal noise, structured bullet points.

## 2. Robustness: `core/workers.py`
I will enhance `TranslationWorker` to be "Smart" about validation.
- **Deep Copy**: Pass a deep copy of `profile` to the worker to avoid thread race conditions.
- **Post-Processing Validation**:
    - **Placeholder Check**: Compare `{n}` tags in source vs. target.
    - **Retry Logic**: If tags mismatch or JSON is invalid:
        - Trigger a "Repair Request" (one retry attempt) with a specific instruction: "Fix the placeholders/JSON format for ID X".
- **JSON Parsing**: Use `json_repair` (or robust `try-except` block with regex fallback) to handle malformed LLM output.

## 3. Integration
- **`desktop_app.py`**:
    - Update `start_translation` to deep copy `self.current_profile` before passing to `TranslationWorker`.

## 4. Testing (`tests/test_prompt_builder.py`)
- **Test 1: Profile Injection**: Verify that specific profile settings (e.g., "Formal") appear in the generated system prompt.
- **Test 2: Profile=None**: Verify behavior matches the "Legacy/Default" mode (simple prompt).
- **Test 3: Placeholder Rules**: Verify the placeholder instruction is always present.
- **Test 4: JSON Structure**: Verify the prompt requests the correct JSON structure.
- **Test 5: Validator Logic**: Test the "Placeholder Check" function (independent unit test).

## 5. Implementation Steps
1.  **Create `core/prompt_builder.py`**: Implement builder and validation logic.
2.  **Update `core/workers.py`**: Integrate builder, add retry loop, and placeholder validation.
3.  **Update `desktop_app.py`**: Pass profile copy.
4.  **Test**: Run `tests/test_prompt_builder.py`.
