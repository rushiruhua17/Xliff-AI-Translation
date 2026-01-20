# Walkthrough - XLIFF AI Assistant

## V2.2 Enhanced QA System & Auto-Repair

### ✅ Phase 1: QA 护栏 (Completed)
- **Validation**: Token Set Matching (`{0}` vs `{0}`) & Invalid Token Detection (`{01}`).
- **UI**: Added "Details" column, Error highlights (Red/Yellow), and blocking Export Gate.
- **Safety**: Fixed Access Violation crashes during QA loop.

### ✅ Phase 2: Auto-Repair (Completed)

#### 1. **"Tiered AI" Architecture** 🧠
- **Concept**: Use separate models for different tasks to balance cost/performance.
- **Settings**: New "Auto-Repair" section in Settings Tab.
  - **Main Model**: High capability (e.g., Claude/GPT-4) for translation.
  - **Repair Model**: Faster/Cheaper (e.g., DeepSeek/Qwen) specifically for fixing tags.
  - **API Key**: Independent configuration for repair model.

#### 2. **Batch Auto-Repair Workflow** 🔧
- **Trigger**: Click `🔧 Batch Auto-Repair` in the toolbar (only appears if errors exist).
- **Process**:
  1. Identifies all segments with critical QA errors.
  2. Extracts required tokens (`{0}, {1}`) from source.
  3. Sends to Repair Model with **Strict Token Preservation Prompt**.
  4. Updates target text only if repair is successful.
- **Verification**: Automatically re-runs QA after repair completes to verify fixes.
- **Progress**: Shows real-time progress bar.

#### 3. **Smart Repair Logic (`repair_segment`)**
- Uses a specialized prompt that forbids re-translation.
- Focuses purely on inserting missing tokens or removing extra ones.
- Enforces strict `{n}` format.

### How to Test
1. **Enable**: Go to Settings -> Enable Auto-Repair -> Set Model (e.g., `deepseek-chat`) & API Key.
2. **Break**: Intentionally delete a tag in a segment (e.g., remove `{0}`).
3. **QA**: Click `Run QA` -> See Red error row.
4. **Repair**: Click `🔧 Batch Auto-Repair` -> Confirm -> Watch it fix!
