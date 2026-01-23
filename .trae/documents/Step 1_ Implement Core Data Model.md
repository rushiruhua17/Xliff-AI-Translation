# Phase 2: Logic Layer (Refined)

Based on your feedback, I have refined the design for the Profile Manager and Sidecar Logic.

## 1. Data Model Updates (`core/profile.py`)
- **Add Status Field**: Update `ControlsConfig` to include a `status` field (Enum: `new`, `draft`, `confirmed`) to explicitly track the profile's lifecycle state for the UI.
  - Default for factories will be `draft` (or `new` for clean templates).
- **Ensure Schema Stability**: Maintain `TranslationProfileContainer` as the root object with `schema_version="1.0"`.

## 2. Profile Manager (`core/profile_manager.py`)
I will implement a robust `ProfileManager` class with the following logic:

### Loading Strategy (`load_profile`)
1.  **Primary**: Attempt to load `<xliff_filename>.profile.json` (Sidecar).
2.  **Secondary**: If Sidecar is missing, attempt to load from **AppData/Global Store** (using a hash of the file path) to handle cases where the source directory was read-only previously.
3.  **Fallback (Memory Only)**: If neither exists, generate a default "Manual" profile in memory.
    - **Crucial**: Set status to `new`/`draft`.
    - **Crucial**: Do **NOT** write this default to disk automatically.

### Saving Strategy (`save_profile`)
1.  **Primary**: Attempt to write to `<xliff_filename>.profile.json` (Sidecar).
2.  **Fallback**: If writing fails (e.g., `PermissionError`, Read-only network share), write to the **AppData/Global Store**.
    - Log a warning so the user (or UI) knows the profile is stored locally, not with the file.

## 3. Testing (`tests/test_core_profile_manager.py`)
I will add specific test cases for:
- **No Sidecar**: Verify `load_profile` returns a valid container with `status='new'` and **no file is created**.
- **Write Protection**: Simulate a read-only directory and verify `save_profile` successfully falls back to the AppData directory.
- **Corrupt Data**: Create a dummy JSON file with invalid syntax or version mismatch and verify the system catches the error, logs it, and returns a safe fallback (no crash).

## 4. Documentation
- Create `sample_profile.json` reflecting the updated schema (with `status`).
