# Phase 3: UI Layer - Project Setup Wizard (Refined)

I will implement the "Project Setup Wizard" incorporating your feedback regarding the collapsible widget, dirty state protection, result codes, data completeness, and testing strategy.

## 1. New Module: `ui/profile_wizard.py`

### Helper: `CollapsibleBox`
I will implement a custom `CollapsibleBox` (inheriting `QWidget`) instead of using `QGroupBox.setCheckable`.
- **UI**: A header button (tool button style with arrow icon) and a content area.
- **Behavior**: Clicking the button toggles `content_area.setVisible()`, effectively hiding the advanced fields to reduce visual clutter.

### Class: `ProfileWizardDialog(QDialog)`
- **Structure**: `QStackedLayout` (Step 1 -> Step 2).
- **State Management**:
    - `self.original_profile`: Deep copy of input profile.
    - `self.working_profile`: The profile being edited.
    - `self.is_dirty`: Boolean flag tracking if user modified fields manually.

### Step 1: Project Info
- Standard form layout for `ProjectMetadata`.

### Step 2: Translation Brief
- **Template Selector**: `QComboBox` + "Apply" Button (or logic to confirm overwrite).
    - **Dirty Protection**: If `self.is_dirty` is True, switching templates triggers a `QMessageBox` ("Discard changes?").
- **Core Fields**: Audience, Tone, Formality, Locale.
- **Advanced Section (CollapsibleBox)**:
    - **Terminology**: Strictness (Combo), Allow Explanation (Check), Use Termbase (Check).
    - **Formatting**: Number preservation, Date preservation.
    - **Logic**: Ensure these inputs map correctly to the nested `FormattingRules` and `TerminologyPolicy` objects in the `TranslationProfile`, maintaining data integrity.

### Result Handling
- **Enums**: Define `WizardResult.ACCEPTED`, `WizardResult.SKIPPED`, `WizardResult.CANCELLED`.
- **Buttons**:
    - **Finish**: Returns `ACCEPTED`.
    - **Skip**: Returns `SKIPPED`.
    - **Cancel (X)**: Returns `CANCELLED`.

## 2. Integration: `desktop_app.py`
- **Logic**:
    - If `status == NEW`: Launch Wizard.
    - **Handle Result**:
        - `ACCEPTED`: Update `current_profile`, set `status=CONFIRMED`, **Save to Sidecar**.
        - `SKIPPED`: Keep `status=NEW` (or `DRAFT`), **Do NOT Save**. Next time it opens, it will prompt again (desired behavior for "Skip").
        - `CANCELLED`: Close file/Cancel open operation (standard behavior for cancelling an import wizard).

## 3. Testing Strategy
- **Logic Layer (`tests/test_ui_logic.py`)**:
    - Test "Template Application": Verify that applying a template to a profile object correctly updates fields while preserving `ProjectMetadata`.
    - Test "Dirty Detection": Verify modification tracking logic (if abstracted).
- **UI Layer (`tests/test_ui_smoke.py`)**:
    - Use `pytest-qt` (if available, or standard `unittest` with `QApplication` instance) to perform a smoke test:
        - Instantiate Dialog.
        - Click "Next".
        - Click "Skip".
        - Verify return code.
    - *Note*: I will ensure tests are robust against headless environments by focusing on logic verification where possible.

## 4. Implementation Order
1.  Create `ui/components.py` for `CollapsibleBox` (reusable).
2.  Create `ui/profile_wizard.py`.
3.  Update `desktop_app.py` integration.
4.  Add tests.
