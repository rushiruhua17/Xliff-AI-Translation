# Phase 4: Finalize Persistence & Fix UI State

I have successfully identified the issue causing the `AttributeError`. It seems my previous attempts to patch `setup_translate_tab` in `desktop_app.py` were not fully applied or were overwritten, leaving `lbl_profile_info` undefined in the `__init__` flow.

## 1. Fix `desktop_app.py` (Critical)
- **Action**: I will meticulously re-apply the changes to `setup_translate_tab` to ensure `self.lbl_profile_info` and `self.profile_card` are instantiated.
- **Verification**: Run `tests/test_flow_integration.py` immediately after fixing.

## 2. Implement Smart Defaults (Phase 4 Goal)
Once the UI is stable, I will implement the requested persistence features in `ui/profile_wizard.py`.

- **Load Defaults**:
    - In `ProfileWizardDialog.__init__` or `load_data`:
    - Read `QSettings` keys: `last_template_id`, `last_locale`.
    - If `self.working_profile.controls.status == NEW` (i.e., first time), override the default values with these settings.

- **Save Defaults**:
    - In `go_next` (Accept step):
    - Save current selections to `QSettings`.

## 3. Verification
- **Integration Test**: I will add a new test case `test_smart_defaults` to `tests/test_flow_integration.py` to verify that opening a new file inherits settings from a previously configured one.

## 4. Execution Steps
1.  **Fix**: Apply UI components to `desktop_app.py`.
2.  **Verify**: Run existing integration tests.
3.  **Implement**: Smart defaults logic in `ui/profile_wizard.py`.
4.  **Test**: Add and run `test_smart_defaults`.
