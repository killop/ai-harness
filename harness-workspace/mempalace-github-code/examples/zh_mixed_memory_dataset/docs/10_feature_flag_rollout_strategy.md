# Feature Flag Rollout Strategy / 渐进发布策略

## 背景 / Background
This document records the design context for `feature-flag-service`.
中文摘要：渐进发布策略，当前设计与 room hint `operations` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `roll out by cohort and region`，而不是 `global enable at midnight`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `feature-flag-service`
- room hint: `operations`
- unique marker: `FLAG_ROLLOUT_STAGE_1_5_20_50_100`
- snippet token: `stages = [1, 5, 20, 50, 100]`

```text
stages = [1, 5, 20, 50, 100]
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 灰度 / 发布 / 回滚 / 分批
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
