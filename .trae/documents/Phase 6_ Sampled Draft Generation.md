# Phase 6 Refined: Robust Profile Auto-Detection

I will implement the "Auto-Detect" feature in the Profile Wizard using the `sampled_draft` strategy, adhering to the strict robustness and architectural requirements.

## 1. Core: `core/profile_generator.py`
- **Input**: List of all `TranslationUnit`s (to sample from), `source_lang`, `target_lang`.
- **Sampling Logic (`sample_segments`)**:
    - **Parameters**: `max_segments=20`, `token_cap=1500` (approx), `seed=None`.
    - **Process**:
        1.  Filter out empty/short segments.
        2.  Take first 5 segments (Context).
        3.  Randomly sample `N` segments from the rest (using `random.Random(seed)`).
        4.  Use `source_abstracted` (de-noised view) as requested.
        5.  Concatenate and truncate if exceeding token cap (approx 4 chars/token).
- **Prompt Logic (`generate_profile_draft`)**:
    - **Prompt**: "Analyze these text samples and generate a translation profile JSON...".
    - **Schema**: Must match `TranslationProfileContainer` structure (excluding `project_metadata` fields like `domain` unless we map them explicitly).
        - **Target Fields**: `content_type`, `target_audience`, `tone_of_voice`, `formality`.
        - **Metadata**: Ask for `domain` and `subject` separately to map to `ProjectMetadata`.
    - **Output**: Strict JSON (using `response_format={"type": "json_object"}` if available).

## 2. Worker: `core/workers.py`
- **Class**: `ProfileGenWorker(QThread)`.
- **Input**: List of units (read-only access or copy), client.
- **Output**: `finished(dict)` signal (returns the raw profile dict/JSON, NOT the object).
- **Process**: Call `ProfileGenerator.generate_profile_draft`.

## 3. UI: `ui/profile_wizard.py`
- **Button**: Add "✨ Auto-Detect Profile" button at the top of Step 2 (or Step 1?).
    - *Decision*: Step 2 is where the Profile fields are. Step 1 is Metadata.
    - *Better*: Add it to Step 1 or a dedicated "Pre-Step"?
    - *User Pref*: "向导 Step 2 顶部提供 Auto-Detect".
    - *Refinement*: Since it detects `domain`/`subject` (Step 1) AND `tone`/`audience` (Step 2), maybe a button on Step 1 "✨ Auto-Fill with AI"?
    - *Plan*: Add button to Step 1. If clicked, it generates and fills BOTH Step 1 (Metadata) and Step 2 (Profile) fields.
- **Loading State**: Disable inputs and show "Analyzing..." while worker runs.
- **Application**: On success, parse the dict into a temp `TranslationProfileContainer` and update UI fields.

## 4. Verification (`tests/test_profile_generator.py`)
- **Test 1: Sampling**: Verify `sample_segments` returns correct count, uses abstracted source, and respects seed (reproducibility).
- **Test 2: Token Cap**: Verify truncation logic.
- **Test 3: Schema Alignment**: Mock LLM response and verify it parses into `TranslationProfileContainer` correctly.

## 5. Implementation Steps
1.  **Create `core/profile_generator.py`**: Implement sampling and generation logic.
2.  **Update `core/workers.py`**: Add `ProfileGenWorker`.
3.  **Update `ui/profile_wizard.py`**: Add "Auto-Detect" button and connection logic.
4.  **Test**: Create `tests/test_profile_generator.py`.
