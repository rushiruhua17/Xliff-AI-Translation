# Phase 4: Fix & Finalize Persistence

I acknowledge the previous error in `desktop_app.py` where `update_profile_ui` was missing. I will fix this first, then implement the "Smart Defaults" requirement for Phase 4.

## 1. Fix `desktop_app.py`
- **Restore Methods**: Re-implement `update_profile_ui` and `edit_profile` which were lost in the file edit process.
- **Verify**: Run `tests/test_flow_integration.py` to confirm the fix.

## 2. Implement Smart Defaults (Phase 4)
- **Goal**: Remember `template_id` and `locale_variant` for the next new file.
- **Mechanism**: Use `QSettings` in `ProfileWizardDialog`.
    - **Load**: In `__init__` or `load_data`, check `QSettings` for `last_template` and `last_locale`. If the current profile is blank/default, apply these overrides.
    - **Save**: In `go_next` (Finish step), save the selected template and locale to `QSettings`.

## 3. Test Plan
- **Integration Test**: Update `tests/test_flow_integration.py` to include a test case for "Smart Defaults":
    1.  Open File A -> Wizard -> Select "Warranty" & "fr-FR" -> Finish.
    2.  Open File B (New) -> Wizard -> Verify "Warranty" and "fr-FR" are pre-selected.

## 4. Execution Order
1.  **Fix**: `desktop_app.py` (add missing methods).
2.  **Verify**: Run integration tests.
3.  **Implement**: Smart defaults in `ui/profile_wizard.py`.
4.  **Verify**: Run updated integration tests.
