# Token Refresh Spec / refresh token 设计说明

## 背景 / Background
This document records the design context for `auth-service`.
中文摘要：refresh token 设计说明，当前设计与 room hint `auth` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `keep current and previous token hash`，而不是 `pure stateless JWT refresh`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `auth-service`
- room hint: `auth`
- unique marker: `AUTH_REFRESH_PREVIOUS_HASH_V1`
- snippet token: `REFRESH_GRACE_WINDOW_MS = 30000`

```text
REFRESH_GRACE_WINDOW_MS = 30000
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 刷新 / 会话 / 并发 / 回放攻击
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
