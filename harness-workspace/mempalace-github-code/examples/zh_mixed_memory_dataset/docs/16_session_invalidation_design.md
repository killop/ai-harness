# Session Invalidation Design / 会话失效设计

## 背景 / Background
This document records the design context for `session-invalidation`.
中文摘要：会话失效设计，当前设计与 room hint `auth` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `fan out revoke event through session index`，而不是 `wait for token expiry only`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `session-invalidation`
- room hint: `auth`
- unique marker: `SESSION_REVOKE_FANOUT_V3`
- snippet token: `emit("SESSION_REVOKED", {"user_id": user_id})`

```text
emit("SESSION_REVOKED", {"user_id": user_id})
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 会话 / 失效 / 登出 / 批量吊销
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
