# Search Ranking Notes / 混合检索实现说明

## 背景 / Background
This document records the design context for `search-ranking`.
中文摘要：混合检索实现说明，当前设计与 room hint `search` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `hybrid retrieval with lexical rerank`，而不是 `vector only retrieval`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `search-ranking`
- room hint: `search`
- unique marker: `SEARCH_CJK_GRAM_2_3`
- snippet token: `rank_score = semantic * 0.38 + lexical * 0.62`

```text
rank_score = semantic * 0.38 + lexical * 0.62
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 检索 / 排序 / 召回 / 中文分词
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
