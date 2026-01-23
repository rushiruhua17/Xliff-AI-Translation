# Phase 7 Refined: Persistent Profile Dock

I will implement the "Translation Context" dock widget with strict behavioral constraints as requested.

## 1. UI Implementation: `desktop_app.py`
- **Component**: `TranslationContextDock(QDockWidget)`.
- **Logic**:
    - Check if parent is `QMainWindow`. Since `desktop_app.py`'s `MainWindow` inherits from `QMainWindow`, I will use `QDockWidget` directly.
    - **Constraints**: 
        - `setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)` (prevents closing/floating).
        - `setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)`.
    - **Content**:
        - A structured `QFormLayout` or `QVBoxLayout` with `QLabel`s for the summary fields.
        - "Edit" button at the bottom.
        - **Styling**: Clean, readable, slightly contrasting background.
- **Integration**:
    - In `MainWindow.__init__`: Call `setup_profile_dock()`.
    - In `update_profile_ui`: Update the labels in the dock.

## 2. Test Plan: `tests/test_ui_structure.py` (New)
I will create a focused test using `unittest` (simulating `qtbot` checks by inspecting widget state) since I cannot easily install `pytest-qt` in this environment (assuming standard lib `unittest` preference unless `pytest` is available).
- **Assertions**:
    - Dock exists and is visible.
    - Dock features are restricted (no float/close).
    - Labels update correctly when `current_profile` changes.

## 3. Implementation Steps
1.  **Modify `desktop_app.py`**: Add `TranslationContextDock` class and integrate it.
2.  **Verify**: Create `tests/test_ui_structure.py` to check dock properties and content updates.
