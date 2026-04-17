# Rate Limiter Design / 限流设计说明

## 背景 / Background
This document records the design context for `gateway-rate-limiter`.
中文摘要：限流设计说明，当前设计与 room hint `architecture` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `token bucket per tenant`，而不是 `single global fixed window`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `gateway-rate-limiter`
- room hint: `architecture`
- unique marker: `TOKEN_BUCKET_GLOBAL_BREAKER_V1`
- snippet token: `allow = bucket.try_consume(tokens=1)`

```text
allow = bucket.try_consume(tokens=1)
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 限流 / 租户 / 熄断 / 网关
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
