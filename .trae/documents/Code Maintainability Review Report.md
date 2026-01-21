# Refactoring Plan: Improving Maintainability

I will execute the proposed changes to modularize the code further.

## 1. Extract Worker Classes (`core/workers.py`)
-   **Action**: Create `core/workers.py`.
-   **Content**: Move the following classes from `desktop_app.py` to `core/workers.py`:
    -   `TranslationWorker`
    -   `RefineWorker`
    -   `TestConnectionWorker`
    -   (Note: `RepairWorker` is already in `core/repair.py`)
-   **Dependencies**: Fix imports in the new file (needs `PyQt6.QtCore`).

## 2. Externalize Prompts (`ai/prompts.py`)
-   **Action**: Create `ai/prompts.py`.
-   **Content**: Extract hardcoded prompt strings from `ai/client.py` into constant variables (e.g., `TRANSLATION_SYSTEM_PROMPT`, `REPAIR_PROMPT_TEMPLATE`).
-   **Update**: Modify `ai/client.py` to import and use these constants.

## 3. Cleanup `desktop_app.py`
-   **Action**:
    -   Remove the moved Worker classes.
    -   Import them from `core.workers`.
    -   This will reduce the file size and improve readability.

## 4. Verification
-   **Action**: Run existing tests (`pytest tests/`) and manually verify the application starts and basic functions (Open, Translate, Repair) work to ensure no import errors were introduced.
