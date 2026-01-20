# Refactoring Plan: Modularization & UI Enhancement

I have analyzed the `desktop_app.py` and project structure. I agree with the proposed refactoring to move QA and Repair logic to the `core/` directory and enhance the UI.

## 1. Core Logic Modularization

### A. Create `core/qa.py`
This module will handle all validation logic, decoupling it from the UI.
-   **Class `QAChecker`**:
    -   Encapsulates regex patterns (`valid_token_pattern`, `invalid_token_pattern`).
    -   Method `check_unit(unit: TranslationUnit) -> QAResult`:
        -   Performs Token Set Matching (missing/extra tokens).
        -   Performs Invalid Token Detection.
        -   Checks for empty translations.
        -   Returns validation status ('ok', 'warning', 'error') and details.
-   **Dependencies**: `re`, `core.xliff_obj.TranslationUnit` (for type hinting).

### B. Create `core/repair.py`
This module will house the background worker for batch repairs.
-   **Migrate `RepairWorker` class**:
    -   Move the `RepairWorker` class from `desktop_app.py` to here.
    -   **Fix**: Remove the local `import re` inside the loop and place it at the module level.
-   **Dependencies**: `PyQt6.QtCore` (QThread, pyqtSignal), `re`.

## 2. UI Enhancements (`desktop_app.py`)

### A. Integrate New Modules
-   Import `QAChecker` from `core.qa`.
-   Import `RepairWorker` from `core.repair`.
-   Refactor `MainWindow.run_qa()` to delegate logic to `QAChecker`.

### B. QA Review Tab Improvements
-   **Context Menu**:
    -   Add `customContextMenuRequested` signal to the QA Table.
    -   Menu Actions:
        -   `🔧 Repair Segment`: Triggers single-segment repair.
        -   `✏️ Quick Edit`: Jumps to the editor for that segment.
-   **Double-Click Navigation**:
    -   Connect `doubleClicked` signal to a handler that locates the unit in the main editor list and scrolls to it.

### C. Export Readiness Panel
-   Add a **Status Dashboard** (likely at the top of the QA tab or main window):
    -   **Health Bar**: A visual progress bar showing Error-free % vs Errors.
    -   **Stats Counters**: Explicit counts for "Errors" (Blocking) and "Warnings" (Non-blocking).

## 3. Verification Plan

### A. Automated Tests
-   **New Test**: `tests/test_core_qa.py`
    -   Test `QAChecker` with various scenarios (perfect match, missing tokens, malformed tokens).
-   **Existing Test**: Run `pytest tests/test_core_mvp.py` to ensure no regressions in parsing/generation.

### B. Manual Verification
-   Load a sample XLIFF file.
-   Run QA check and verify the Readiness Panel updates correctly.
-   Test the Context Menu (Repair/Edit) on a failed segment.
