# Phase 3.5 Verification: Integration Tests

I will now verify the critical user flows by running the integration tests I have prepared and fixed.

## Current State
- **UI Refinement**: The "Translation Brief Card" with status badge and edit button has been added to `desktop_app.py`.
- **Test Implementation**: `tests/test_flow_integration.py` simulates the full "Skip" and "Save & Restart" flows.
- **Bug Fix**: I have resolved the `AttributeError` in the test setup and the patching issues with `ProfileWizardDialog`.

## Plan
1.  **Run Tests**: Execute `python -m unittest tests/test_flow_integration.py`.
2.  **Verify Output**: Ensure both tests pass:
    - `test_skip_flow`: Verifies "Temporary" status and no sidecar.
    - `test_finish_save_restart_flow`: Verifies "Confirmed" status, sidecar creation, and persistence after restart.
3.  **Final Confirmation**: Report the success of these tests as proof that Phase 3 is robust and ready for Phase 4.
