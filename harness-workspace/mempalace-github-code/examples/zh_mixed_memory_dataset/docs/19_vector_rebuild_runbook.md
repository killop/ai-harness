# Vector Rebuild Runbook / 向量索引重建手册

## 背景 / Background
This document records the design context for `vector-rebuild`.
中文摘要：向量索引重建手册，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `backup metadata and rebuild collection in batches`，而不是 `delete palace and re-mine immediately`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `vector-rebuild`
- room hint: `operations`
- unique marker: `VECTOR_REBUILD_BATCH_5000`
- snippet token: `new_col.add(documents=batch["documents"], ids=batch["ids"], metadatas=batch["metadatas"])`

```text
new_col.add(documents=batch["documents"], ids=batch["ids"], metadatas=batch["metadatas"])
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 重建 / 备份 / 修复 / 批量恢复
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
