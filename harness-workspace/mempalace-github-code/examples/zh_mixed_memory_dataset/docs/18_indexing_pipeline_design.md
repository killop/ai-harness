# Indexing Pipeline Design / 索引流水线设计

## 背景 / Background
This document records the design context for `indexing-pipeline`.
中文摘要：索引流水线设计，当前设计与 room hint `search` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `pending current archived snapshot states`，而不是 `direct write into live index`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `indexing-pipeline`
- room hint: `search`
- unique marker: `INDEX_SNAPSHOT_SWITCH_0900`
- snippet token: `switch_current_snapshot(snapshot_id)`

```text
switch_current_snapshot(snapshot_id)
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 索引 / 快照 / 原子切换 / 重建
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
