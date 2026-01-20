# Enhanced QA System & Auto-Repair (v2.2)

## 🎯 Goal
Implement industrial-grade QA护栏 to prevent broken XLIFF exports, with optional AI-powered Auto-Repair.

## 📊 AI Error Risk Assessment
基于现代 LLM 的表现：
- **基础准确率**：90-95%（GPT-4/DeepSeek-V3 处理 `{n}` 占位符）
- **风险场景**：
  - 大文件（500+ 条）批量翻译时偶发遗漏
  - 复杂嵌套标签（3+ 层）时顺序错误
  - 部分 provider（如某些国产小模型）指令遵循能力弱
- **结论**：**中等风险**，Auto-Repair 作为可选功能合理

---

## 🏗️ Architecture: "分级 AI" 策略

### 核心理念
不同任务用不同模型，优化成本/效果比：
- **翻译任务**（Primary）：GPT-4, DeepSeek-V3（贵但质量高）
- **Repair 任务**（Secondary）：GPT-3.5-turbo, Qwen-2.5-mini（便宜快，任务简单）

### Settings 配置项
```
[Translation Model]
  Provider: SiliconFlow
  Model: deepseek-ai/DeepSeek-V2.5

[Repair Model] (Optional, if Auto-Repair enabled)
  Provider: OpenAI
  Model: gpt-3.5-turbo
  
[Auto-Repair Settings]
  ☑ Enable Auto-Repair
  Max Retry: 2
```

---

## 📅 Implementation Plan

### Phase 1: 强化 QA 护栏（必须）

#### 1.1 升级 `run_qa()` 检查逻辑
**当前问题**：只检查数量，不检查具体值。

**新增检查**：
- **A. Token Set Matching**（核心）
  ```python
  source_tokens = set(re.findall(r"\{\d+\}", unit.source_abstracted))
  target_tokens = set(re.findall(r"\{\d+\}", unit.target_abstracted))
  
  missing = source_tokens - target_tokens  # {0}, {2}
  extra = target_tokens - source_tokens    # {99}
  ```
  
- **B. Token 形态校验**
  ```python
  # 禁止非法形态
  invalid_pattern = r"\{(?![\d]+\})"  # {01}, { 1 }, {x}, {{1}}
  if re.search(invalid_pattern, target):
      qa_status = "error"
  ```

- **C. 成对标签嵌套（可选，Phase 2）**
  - 需解析 `tags_map`，Stack-based 括号匹配
  - 复杂度高，暂不实现

**输出细化**：
```python
unit.qa_details = {
    "missing_tokens": ["{0}", "{2}"],
    "extra_tokens": ["{99}"],
    "invalid_tokens": ["{ 1 }"]
}
```

#### 1.2 UI 增强
- **Tag Details 列**：显示 "Missing: {0}, {2}"
- **导出统计**：顶部显示 "✅ Safe: 45 / ⚠️ Warning: 3 / ⛔ Error: 2"
- **标红行**：Error 行背景色设为浅红

---

### Phase 2: Auto-Repair（可选功能）

#### 2.1 Settings UI
在 Settings Tab 新增 GroupBox：
```
[Auto-Repair]
  ☑ Enable Auto-Repair
  Repair Model: [Dropdown: gpt-3.5-turbo / deepseek-chat-mini]
  API Key: [Password Field]
  Base URL: [Optional]
```

#### 2.2 Repair Prompt 设计
```python
prompt = f"""You are a XLIFF tag fixer. Your ONLY task is to fix missing/extra placeholder tokens.

**Rules**:
1. You MUST include ALL tokens from the required list EXACTLY ONCE.
2. Do NOT add, remove, or modify any tokens.
3. Do NOT translate the text again.
4. Only adjust the position/presence of tokens.

**Required Tokens**: {{{", ".join(source_tokens)}}}
**Current (Broken) Translation**: {unit.target_abstracted}

Output ONLY the fixed translation, nothing else.
"""
```

#### 2.3 Repair Workflow
```python
def auto_repair_segment(unit):
    if not settings["auto_repair_enabled"]: return False
    
    repair_client = LLMClient(
        api_key=settings["repair_api_key"],
        model=settings["repair_model"]
    )
    
    fixed_target = repair_client.repair_segment(
        source=unit.source_abstracted,
        broken_target=unit.target_abstracted,
        required_tokens=extract_tokens(unit.source_abstracted)
    )
    
    unit.target_abstracted = fixed_target
    return True  # Re-run QA after repair
```

#### 2.4 UI 集成
- **Context Menu**：新增 "🔧 Auto-Repair Selected"
- **Batch Repair**：`run_qa()` 后弹窗："发现 5 个错误，是否批量修复？"

---

### Phase 3: UI 美化（体验优化）

#### 3.1 QA Tab（专用质检视图）
- 表格显示所有有问题的 Unit
- 列：ID / Source / Target / Issue Type / Action
- Action Button："🔧 Repair" / "✏️ Edit" / "❌ Ignore"

#### 3.2 导出前统计面板
```
┌─────────────────────────────┐
│ Export Readiness            │
├─────────────────────────────┤
│ ✅ Safe to Export:      45  │
│ ⚠️  Warnings:            3  │
│ ⛔ Critical Errors:      2  │
│                             │
│ [Run QA] [Auto-Repair All]  │
└─────────────────────────────┘
```

---

## 🚨 Critical Technical Details

### 1. `LLMClient` 扩展
需要支持"双模型配置"：
```python
class LLMClient:
    def __init__(self, api_key, model, base_url=None, provider="custom"):
        # Primary config
        
    @classmethod
    def create_repair_client(cls, settings):
        # Secondary config for repair
        return cls(
            api_key=settings["repair_api_key"],
            model=settings["repair_model"],
            ...
        )
```

### 2. Settings 持久化
```python
# 新增字段
settings.setValue("auto_repair_enabled", True)
settings.setValue("repair_model", "gpt-3.5-turbo")
settings.setValue("repair_api_key", "sk-...")
```

### 3. 性能优化
- Repair 不应阻塞 UI（使用 `QThread`）
- 批量 Repair 时显示进度条

---

## 📝 User Review Required

> [!IMPORTANT]
> **关键决策点**：
> 1. Auto-Repair 默认**关闭**还是**开启**？（建议默认关闭）
> 2. Repair Model 默认值？（建议 `gpt-3.5-turbo`）
> 3. 是否允许用户为 Repair 配置独立 API Key？（避免混用额度）
