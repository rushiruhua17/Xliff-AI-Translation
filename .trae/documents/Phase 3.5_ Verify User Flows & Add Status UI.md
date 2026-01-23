# Phase 3.5: User Flow Verification & UI Refinement

I will verify the two critical user flows requested and ensure the UI reflects the profile status correctly.

## 1. UI Refinement: Translation Brief Card
Currently, `desktop_app.py` does not display the "Translation Brief Card" mentioned in the user flow. I need to add this visualization to the main window so the user can see the status ("Unconfigured/Temporary" vs. "CONFIRMED").

- **Modify `desktop_app.py`**:
    - Add a `QFrame` or `QGroupBox` to the sidebar (or top bar) to display the active profile summary.
    - **Visuals**:
        - **Label**: "Profile: [Template Name]"
        - **Status Badge**:
            - `CONFIRMED`: Green check or "Confirmed".
            - `NEW`/`DRAFT`: Orange/Yellow "Temporary Default" or "Unconfigured".
        - **Button**: "Edit" (triggers the Wizard again).

## 2. Verification Test Plan (`tests/test_flow_integration.py`)
I will create a new integration test file to simulate these flows programmatically (avoiding manual GUI clicking for reproducibility).

### Test 1: Skip Flow (Temporary Profile)
1.  **Setup**: Create a temporary dummy XLIFF file.
2.  **Action**:
    - Initialize `MainWindow`.
    - Call `open_file` logic (mocking the Wizard execution to return `SKIPPED`).
3.  **Verification**:
    - Assert `self.current_profile.controls.status` is `NEW` (or `DRAFT`).
    - Assert **No Sidecar File** exists on disk.
    - Assert UI Card shows "Temporary" status.

### Test 2: Finish/Save Flow (Persistence)
1.  **Setup**: Use the same XLIFF file.
2.  **Action**:
    - Call `open_file` (mocking Wizard to return `ACCEPTED`).
3.  **Verification**:
    - Assert `self.current_profile.controls.status` is `CONFIRMED`.
    - Assert **Sidecar File Exists**.
4.  **Restart Simulation**:
    - Close and re-initialize `MainWindow`.
    - Call `open_file` again.
5.  **Verification**:
    - Assert Wizard is **NOT** triggered (mock should not be called).
    - Assert Profile loaded from disk is `CONFIRMED`.
    - Assert UI Card shows "Confirmed".

## 3. Implementation Steps
1.  **Update `desktop_app.py`**: Implement the "Translation Brief Card" UI component.
2.  **Create `tests/test_flow_integration.py`**: Implement the simulation tests.
3.  **Run Tests**: Execute and report results.
