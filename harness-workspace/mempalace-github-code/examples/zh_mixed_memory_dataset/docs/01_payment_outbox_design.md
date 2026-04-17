# Payment Outbox Design / 支付 outbox 设计

## 背景 / Background
This document records the design context for `payment-service`.
中文摘要：支付 outbox 设计，当前设计与 room hint `architecture` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `use PostgreSQL outbox pattern`，而不是 `sync ledger RPC`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `payment-service`
- room hint: `architecture`
- unique marker: `PAYMENT_OUTBOX_V2_MARKER`
- snippet token: `dedup_key = f"{order_id}:{provider_event_id}"`

```text
dedup_key = f"{order_id}:{provider_event_id}"
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 支付 / 幂等 / 回调 / 重复扣款 / 回滚
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
