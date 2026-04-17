# Cache Strategy ADR / 缓存策略 ADR

## 背景 / Background
This document records the design context for `search-api`.
中文摘要：缓存策略 ADR，当前设计与 room hint `search` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `cache drawer ids only`，而不是 `cache full response body`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `search-api`
- room hint: `search`
- unique marker: `CACHE_DRAWER_ID_ADR_003`
- snippet token: `redis.set(cache_key, json.dumps(topk_ids), ex=120)`

```text
redis.set(cache_key, json.dumps(topk_ids), ex=120)
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 缓存 / 失效 / 旧结果 / 排序
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
