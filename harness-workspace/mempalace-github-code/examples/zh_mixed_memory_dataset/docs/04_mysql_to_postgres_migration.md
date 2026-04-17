# MySQL to PostgreSQL Migration / 数据迁移方案

## 背景 / Background
This document records the design context for `billing-platform`.
中文摘要：数据迁移方案，当前设计与 room hint `data` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `dual write verify switch plan`，而不是 `big bang migration`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `billing-platform`
- room hint: `data`
- unique marker: `PG_MIGRATION_PHASE_SWITCH_V5`
- snippet token: `phase_1 = "dual_write"`

```text
phase_1 = "dual_write"
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 迁移 / 双写 / 切流 / 校验 / 回滚
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
