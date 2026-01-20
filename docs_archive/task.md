# 任务列表：XLIFF 交互式翻译辅助系统

- [x] **Desktop App Optimizations (v2.0)**
    - [x] Persist User Settings (QSettings)
    - [x] Advanced Filtering & Search
    - [x] Keyboard Shortcuts & Navigation
    - [x] **Fix Context Menu & Selective Translation**
    - [x] **Fix Dock Resizing & UI Bugs**
    - [x] **Fix Stability & Crashes**
    - [x] **Add Logging Module** (core/logger.py)
    - [x] **Fix Export Dialog Format** (*.xlf, *.xliff)

- [x] **UI Refactor: Translator Workbench (v2.1)** <!-- id: 24 -->
    - [x] **Core Layout**: Implement Tab Structure (Translate, QA, Assets, Settings) <!-- id: 25 -->
    - [x] **Data Model**: Upgrade XliffTableModel (Add QA status, Tag counts) <!-- id: 26 -->
    - [x] **Workbench Drawer**: Implement Split View (Source + Target + AI Actions) <!-- id: 27 -->
    - [x] **QA System**: Implement QA Checks (Tag mismatch, Empty target) & Error Gate <!-- id: 28 -->
    - [x] **Toolbar**: Add Project Stats & Quick Actions <!-- id: 29 -->

- [ ] **Enhanced QA System & Auto-Repair (v2.2)** <!-- id: 30 -->
    - [x] **Phase 1: QA 护栏** <!-- id: 31 -->
        - [x] Upgrade `run_qa()`: Token Set Matching + Invalid Token Detection <!-- id: 32 -->
        - [x] UI: Tag Details column + Export Readiness Stats <!-- id: 33 -->
        - [x] UI: Highlight Error rows (background color) <!-- id: 34 -->
    - [x] **Phase 2: Auto-Repair (Optional)** <!-- id: 35 -->
        - [x] Settings: Add Auto-Repair toggle + Repair Model config <!-- id: 36 -->
        - [x] Implement `repair_segment()` with Secondary LLM Client <!-- id: 37 -->
        - [x] UI: "Batch Auto-Repair" Button + Worker Thread <!-- id: 38 -->
    - [ ] **Phase 3: UI Polish** <!-- id: 39 -->
        - [ ] Create dedicated QA Tab (Error list view) <!-- id: 40 -->
        - [ ] Export Readiness Panel on Worktable <!-- id: 41 -->

- [ ] **Packaging & Release**
    - [ ] Create standalone executable (PyInstaller)
    - [ ] Upload to GitHub/Release <!-- id: 6 -->
