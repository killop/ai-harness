# Refresh Token Recovery Runbook / refresh 异常恢复手册

## 背景 / Background
This document records the design context for `auth-runbook`.
中文摘要：refresh 异常恢复手册，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `raise grace window temporarily`，而不是 `blindly restart auth service`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `auth-runbook`
- room hint: `operations`
- unique marker: `RUNBOOK_REFRESH_GRACE_WINDOW_30000`
- snippet token: `SELECT session_id FROM refresh_session LIMIT 50;`

```text
SELECT session_id FROM refresh_session LIMIT 50;
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 恢复 / 手册 / 掉线 / 止血
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
