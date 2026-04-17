# Audit Log Retention Policy / audit log 保留策略

## 背景 / Background
This document records the design context for `audit-log`.
中文摘要：audit log 保留策略，当前设计与 room hint `data` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `hot cold layered retention`，而不是 `store all logs in primary db`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `audit-log`
- room hint: `data`
- unique marker: `AUDIT_HOT_90_COLD_ARCHIVE_V2`
- snippet token: `ALTER TABLE audit_log DETACH PARTITION audit_log_2025_12;`

```text
ALTER TABLE audit_log DETACH PARTITION audit_log_2025_12;
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 审计 / 保留 / 归档 / 合规
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
