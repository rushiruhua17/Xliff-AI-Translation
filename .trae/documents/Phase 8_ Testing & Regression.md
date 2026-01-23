# Phase 8 Final: "Bulletproof" Regression Suite

I will execute the testing plan with the specific additions for schema versioning and safe batch processing.

## 1. Refactoring: `core/batch_processor.py` (New)

I will extract the LLM interaction logic into a `BatchProcessor` class.

* **Single Source of Truth**: This class will handle `PromptBuilder` calls, LLM execution, JSON parsing, validation, and retry loops.

* **Safety**: It will return a *result map* (dict of id->text) rather than modifying units directly. The worker/caller decides when to apply.

* **Retry Logic**: It will implement the "count-limited retry" logic for JSON errors and placeholder mismatches.

## 2. Test Suite: `tests/test_profile_system.py`

### A. Data & Schema Integrity

* **Round-Trip**: `asdict` comparison of Profile objects.

* **Template Defaults**: Verify factory defaults (Warranty=Strict, Training=Friendly).

* **Negative Test (Schema Mismatch)**:

  * Save a profile with `schema_version="0.9"`.

  * Load it and verify it either upgrades or falls back safely (does not crash).

* **Negative Test (Corrupted JSON)**:

  * Save a broken JSON file.

  * Verify `load_profile` returns a default profile safely.

### B. Logic & Mocking (BatchProcessor)

* **Success**: Mock `client.chat` -> Valid JSON -> Verify result map is correct.

* **Retry Logic**:

  * Mock `client.chat` to fail once (bad JSON), then succeed.

  * Verify `BatchProcessor` retries and returns success.

* **Failure**:

  * Mock `client.chat` to fail repeatedly.

  * Verify `BatchProcessor` returns empty dict (no partial corruption).

### C. Prompt Regression

* **Contract**: Assert strict JSON schema instructions and placeholder rules exist in `profile=None` and `profile=Full` cases.

## 3. Implementation Steps

1. **Extract**: Create `core/batch_processor.py`.
2. **Update**: Modify `core/workers.py` to use `BatchProcessor`.
3. **Test**: Create `tests/test_profile_system.py` covering all points above.
4. **Verify**: Run suite.

