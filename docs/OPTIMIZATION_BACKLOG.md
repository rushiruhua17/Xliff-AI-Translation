# Optimization & Known Issues Backlog
# 优化与已知问题待办列表

This document tracks optimization requests, known bugs, and feature enhancements that are currently postponed or require further investigation.
本文档用于记录目前暂时搁置或需要进一步调查的优化需求、已知 Bug 和功能增强。

## UI/UX (界面体验)

### [2026-01-30] Sidebar Navigation Tooltip Delay (侧边栏工具提示延迟)
- **Status**: ⏸️ Postponed (暂时搁置)
- **Description**: 
  The tooltip on the left sidebar navigation icons (Home, Project, Editor) has a default delay of ~1 second, which feels sluggish compared to the rest of the optimized UI (50ms).
  侧边栏导航图标的工具提示延迟约为1秒，相比其他已优化的界面（50ms）显得迟钝。
  
- **Technical Notes (技术备注)**:
  - Tried applying `ToolTipFilter` with `showDelay=50` to internal `QAbstractButton` children of `NavigationInterface`.
    尝试对 `NavigationInterface` 内部的 `QAbstractButton` 子组件应用 `showDelay=50` 的 `ToolTipFilter`。
  - Result: Inconsistent behavior on `QFluentWidgets` managed items.
    结果：在 `QFluentWidgets` 管理的组件上表现不一致/未生效。
    
- **Future Plan (后续计划)**:
  - Investigate `NavigationItem` internal event handling.
    调查 `NavigationItem` 的内部事件处理机制。
  - Check for global configuration options in the library.
    检查库中是否存在全局配置选项。

### [2026-01-30] Editor Table ScrollBar Styling (编辑器表格滚动条样式)
- **Status**: ⏸️ Postponed (暂时搁置)
- **Description**: 
  The translation table (`ModernTranslationTable`) currently uses the native OS scrollbar, which looks outdated compared to the Fluent Design style of the rest of the application. The goal is to replace it with `SmoothScrollBar`.
  翻译表格（`ModernTranslationTable`）目前使用的是操作系统原生滚动条，与应用其他部分的 Fluent Design 风格相比显得过时。目标是将其替换为 `SmoothScrollBar`。

- **Technical Notes (技术备注)**:
  - `SmoothScrollBar` in `QFluentWidgets` inherits from `QWidget`, not `QScrollBar`, so it cannot be directly assigned to `QTableView.setVerticalScrollBar()`.
    `QFluentWidgets` 中的 `SmoothScrollBar` 继承自 `QWidget` 而非 `QScrollBar`，因此无法直接赋值给 `QTableView.setVerticalScrollBar()`。
  - Currently applied `SmoothScrollDelegate` to ensure kinetic scrolling, but the visual appearance remains native.
    目前已应用 `SmoothScrollDelegate` 以确保惯性滚动体验，但视觉外观仍保持原生。

- **Future Plan (后续计划)**:
  - Option A: Implement a custom QSS style for `QScrollBar` to mimic Fluent Design.
    方案 A：为 `QScrollBar` 实现自定义 QSS 样式以模仿 Fluent Design。
  - Option B: Refactor the table to use `TableWidget` from `QFluentWidgets` which wraps the scrollbar correctly (high effort).
    方案 B：重构表格以使用 `QFluentWidgets` 提供的 `TableWidget`，它能正确包装滚动条（工作量较大）。

---
