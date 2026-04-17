# API Versioning Contract / API 版本治理

## 背景 / Background
This document records the design context for `public-api`.
中文摘要：API 版本治理，当前设计与 room hint `architecture` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `sunset window for breaking change`，而不是 `rename fields in place`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `public-api`
- room hint: `architecture`
- unique marker: `API_SUNSET_WINDOW_180D`
- snippet token: `response.headers["Sunset"] = "2026-09-30"`

```text
response.headers["Sunset"] = "2026-09-30"
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 版本 / 兼容 / 弃用 / 契约
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
