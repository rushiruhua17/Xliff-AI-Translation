I have analyzed the recurring crash (`Access Violation`).

**Diagnosis:**
The crash is likely caused by **redundant layout updates and unsafe UI event handling** immediately after a modal dialog closes.
1.  In `on_single_repair_finished`, you call `self.model.layoutChanged.emit()` and then immediately call `self.run_qa(silent=True)`.
2.  `run_qa` *also* calls `self.model.layoutChanged.emit()`.
3.  Triggering `layoutChanged` (which forces a full view redraw) twice in rapid succession, especially immediately after a `QMessageBox` closes (which involves event loop re-entry), is a known cause of instability and crashes in PyQt/Qt applications.

**Fix Plan:**

1.  **Refactor `on_single_repair_finished`**:
    *   **Remove** the explicit `self.model.layoutChanged.emit()` call (since `run_qa` handles it).
    *   **Defer** the `run_qa` call using `QTimer.singleShot(0, ...)` to ensure the stack unwinds and the message box is fully cleaned up before refreshing the table.

2.  **Harden Context Menu Callbacks**:
    *   Update the lambda connections to explicitly bind the `index` using default arguments (`idx=index`). This is a safer pattern than relying on closure capture for temporary Qt objects like `QModelIndex`.

3.  **Refactor `run_qa`**:
    *   Ensure `layoutChanged` is emitted only once and at a safe time.

**Verification:**
*   Run the regression tests again.
*   The code changes are defensive and aimed at stabilizing the Qt event loop interaction.

This approach addresses the root cause of "Access Violation" errors in GUI event handlers.
