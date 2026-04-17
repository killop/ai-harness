# Webhook Duplicate Charge Postmortem / 重复扣款复盘

## 背景 / Background
This document records the design context for `payments-incident`.
中文摘要：重复扣款复盘，当前设计与 room hint `incidents` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `compose idempotency key with order_id and provider_event_id`，而不是 `dedup by order_id only`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `payments-incident`
- room hint: `incidents`
- unique marker: `POSTMORTEM_DUPLICATE_CHARGE_0410`
- snippet token: `if dedup_log.exists(dedup_key): return "already_processed"`

```text
if dedup_log.exists(dedup_key): return "already_processed"
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 复盘 / 根因 / 补偿交易 / 告警
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
