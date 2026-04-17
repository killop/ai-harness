# Event Consumer Retry Policy / consumer 重试策略

## 背景 / Background
This document records the design context for `event-consumer`.
中文摘要：consumer 重试策略，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `split retry outcome into drop retry dlq`，而不是 `single retryable boolean`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `event-consumer`
- room hint: `operations`
- unique marker: `PAYMENT_EVT_DEDUP_V3`
- snippet token: `return SEND_TO_DLQ`

```text
return SEND_TO_DLQ
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 重试 / 死信 / 回放 / 偏移提交
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
