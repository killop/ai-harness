# Billing Reconciliation Pipeline / 对账流水线

## 背景 / Background
This document records the design context for `billing-reconciliation`.
中文摘要：对账流水线，当前设计与 room hint `data` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `daily reconciliation mismatch buckets`，而不是 `manual spreadsheet compare`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `billing-reconciliation`
- room hint: `data`
- unique marker: `RECON_BATCH_CHECKSUM_GATE_V4`
- snippet token: `bucket = "amount_mismatch"`

```text
bucket = "amount_mismatch"
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 对账 / 金额偏差 / 批次 / 结算
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
