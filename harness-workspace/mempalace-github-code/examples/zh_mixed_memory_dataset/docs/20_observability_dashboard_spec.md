# Observability Dashboard Spec / 可观测性仪表盘说明

## 背景 / Background
This document records the design context for `observability-dashboard`.
中文摘要：可观测性仪表盘说明，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `one release dashboard with error budget and consumer lag`，而不是 `separate dashboard per service only`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `observability-dashboard`
- room hint: `operations`
- unique marker: `DASHBOARD_RELEASE_OVERVIEW_V12`
- snippet token: `panels = ["latency_p95", "error_rate", "consumer_lag"]`

```text
panels = ["latency_p95", "error_rate", "consumer_lag"]
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 仪表盘 / 可观测性 / 延迟 / 错误率
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
