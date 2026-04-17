# Redis Fallback Plan / Redis 降级预案

## 背景 / Background
This document records the design context for `redis-fallback`.
中文摘要：Redis 降级预案，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `bounded local cache fallback`，而不是 `retry Redis on every request`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `redis-fallback`
- room hint: `operations`
- unique marker: `REDIS_LOCAL_FALLBACK_512_KEYS`
- snippet token: `return local_lru.get(key) or fetch_from_primary()`

```text
return local_lru.get(key) or fetch_from_primary()
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 降级 / 缓存 / 超时 / 本地兜底
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
