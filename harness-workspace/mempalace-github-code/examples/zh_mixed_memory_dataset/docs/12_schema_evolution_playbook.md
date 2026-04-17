# Schema Evolution Playbook / schema 演进手册

## 背景 / Background
This document records the design context for `event-schema`.
中文摘要：schema 演进手册，当前设计与 room hint `data` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `append-only schema with version field`，而不是 `replace payload shape in place`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `event-schema`
- room hint: `data`
- unique marker: `SCHEMA_APPEND_ONLY_VERSION_3`
- snippet token: `{"schema_version": 3, "provider_event_id": "evt_9001"}`

```text
{"schema_version": 3, "provider_event_id": "evt_9001"}
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 演进 / 版本 / 向后兼容 / 回放
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
