# Kafka Partition Key Design / partition key 设计

## 背景 / Background
This document records the design context for `kafka-stream`.
中文摘要：partition key 设计，当前设计与 room hint `architecture` 相关。
The current change is motivated by production issues, rollback pressure, and maintainability concerns.

## 决策 / Decision
我们决定采用 `partition by account_id`，而不是 `hash on event_type only`。
Why this works:
- better rollback path
- clearer ownership
- lower operational ambiguity

## Implementation Notes
- system: `kafka-stream`
- room hint: `architecture`
- unique marker: `KAFKA_ACCOUNT_ID_PARTITION_V2`
- snippet token: `producer.send("account-events", key=account_id, value=payload)`

```text
producer.send("account-events", key=account_id, value=payload)
```

## 风险 / Risks
- rollout can increase latency during cold start
- replay jobs may need manual verification after rollback

## 中文关键词 / Chinese Keywords
- 分区键 / 顺序 / 事件流 / 乱序
- 背景 / 决策 / 风险

## English Keywords
- design
- rollback
- implementation notes
- mixed language retrieval
