# MemPalace 存储与查询概览

这份文档总结 `mempalace` 当前代码里的实际实现方式，重点说明两件事：

1. 它是怎么存的
2. 它是怎么查的

一句话版本：

`mempalace` 的核心并不是一套真的按宫殿楼层落盘的复杂存储系统，而是：

- 一份 `ChromaDB` 集合，存所有原文 chunk 和对应 metadata
- 一份 `SQLite` 知识图谱，存结构化事实和时间关系
- 一层 CLI / MCP / MemoryStack 访问层，给模型和工具用

## 总图

```text
                    MemPalace 实际架构

             ┌──────────────────────────────┐
             │        输入数据源            │
             │                              │
             │ 1. 项目文件                  │
             │ 2. 对话导出                  │
             │ 3. 手工写入 drawer / diary   │
             └──────────────┬───────────────┘
                            |
          ┌─────────────────┴─────────────────┐
          |                                   |
          v                                   v
┌──────────────────────┐            ┌──────────────────────┐
│  Project Miner       │            │  Convo Miner         │
│  miner.py            │            │  convo_miner.py      │
│                      │            │                      │
│ 读文件               │            │ normalize 聊天格式   │
│ 路由到 room          │            │ 按 exchange chunk    │
│ 按字符切 chunk       │            │ 检测对话 topic room  │
└──────────┬───────────┘            └──────────┬───────────┘
           |                                   |
           └─────────────────┬─────────────────┘
                             v
                ┌──────────────────────────────┐
                │   Chroma collection          │
                │   mempalace_drawers          │
                │                              │
                │ document  = 原文 chunk       │
                │ embedding = 向量             │
                │ metadata  = wing/room/...    │
                └──────────────┬───────────────┘
                               |
               ┌───────────────┼────────────────┐
               |               |                |
               v               v                v
      searcher.py         layers.py        mcp_server.py
      深度搜索            L0-L3 记忆栈      对外暴露工具

另外一条并行支线:
                ┌──────────────────────────────┐
                │    SQLite Knowledge Graph    │
                │ knowledge_graph.sqlite3      │
                │                              │
                │ entity -> predicate -> entity│
                │ valid_from / valid_to        │
                └──────────────────────────────┘
```

## 1. 存储模型

### 1.1 概念层和实现层的区别

MemPalace 在概念上讲的是：

- `wing`
- `room`
- `drawer`

但在实际实现里，主存储不是一个真的多层目录结构，而是一张平铺的 Chroma 集合记录表。

也就是说，`wing` 和 `room` 主要是 metadata 标签，不是物理存储层级。

```text
概念模型:
  wing -> room -> drawer

实际模型:
  Chroma collection 里的很多条记录
  每条记录:
    - document  = 原文 chunk
    - metadata  = wing / room / source_file / chunk_index / ...
```

示意：

```text
row 1
  doc  = "We decided to use Clerk because..."
  meta = {
    wing: "wing_driftwood",
    room: "auth-migration",
    source_file: "...",
    chunk_index: 0
  }

row 2
  doc  = "Kai debugged OAuth refresh..."
  meta = {
    wing: "wing_kai",
    room: "auth-migration",
    source_file: "...",
    chunk_index: 1
  }
```

### 1.2 项目文件怎么入库

项目文件入库主线在 `mempalace/miner.py`：

```text
项目文件
  -> detect_room()
     先看目录名/文件名，再看关键词
  -> chunk_text()
     按字符切成多个 drawer
  -> add_drawer()
     upsert 到 Chroma
```

更具体一点：

```text
文件系统
  |
  v
scan_project()
  |
  v
process_file()
  |
  +--> file_already_mined()
  |    检查 source_file / source_mtime
  |
  +--> detect_room(filepath, content, rooms, project_path)
  |    路由到某个 room
  |
  +--> chunk_text(content)
  |    默认:
  |      CHUNK_SIZE    = 800
  |      CHUNK_OVERLAP = 100
  |
  +--> add_drawer(...)
       collection.upsert(
         documents=[content_chunk],
         ids=[drawer_id],
         metadatas=[{
           wing,
           room,
           source_file,
           chunk_index,
           added_by,
           filed_at,
           source_mtime
         }]
       )
```

### 1.3 对话怎么入库

对话入库主线在 `mempalace/convo_miner.py` 和 `mempalace/normalize.py`：

```text
聊天导出
  -> normalize()
     把不同格式统一成 transcript
  -> chunk_exchanges()
     一轮 user + assistant 作为一个 chunk
  -> detect_convo_room()
     给对话打 topic room
  -> upsert 到同一个 Chroma collection
```

示意：

```text
Claude / ChatGPT / Slack / Codex 导出
  |
  v
normalize.py
  |
  v
chunk_exchanges()
  |
  v
collection.upsert(
  documents=[exchange_chunk],
  metadatas=[{
    wing,
    room,
    source_file,
    chunk_index,
    added_by,
    filed_at,
    ingest_mode: "convos",
    extract_mode: ...
  }]
)
```

注意：

- 项目文件和对话最终都进入同一个 `mempalace_drawers` 集合
- 差异主要体现在 `metadata`
- 系统强调“原文存储”，不是先总结再存

## 2. 查询模型

### 2.1 它不是纯向量搜索

`mempalace/searcher.py` 现在采用的是：

```text
vector first
  +
lexical fallback
  +
hybrid rerank
```

也就是：

1. 先用 Chroma 向量召回
2. 在特定条件下补做词法扫描
3. 把两路候选合并
4. 再做混合排序

### 2.2 查询链路

```text
用户问题
  |
  v
search_memories(query, wing?, room?)
  |
  +--> build_where_filter()
  |    如果给了 wing / room，先缩小搜索域
  |
  +--> collection.query(...)
  |    做第一轮向量召回
  |
  +--> 如果命中这些情况，触发 lexical fallback
  |      - 向量结果不够
  |      - 中文 / CJK 查询
  |      - ADR / spec / architecture 这类结构化查询
  |
  +--> collection.get(...)
  |    拉一批文档做词法打分
  |
  +--> _merge_candidates()
  |    合并 vector / lexical 候选
  |
  +--> _rank_candidates()
  |    semantic_similarity + lexical_similarity 混排
  |
  v
返回 top N 原文 chunk + metadata
```

### 2.3 排序时看什么

最终排序不是只看 embedding 距离。

它还会看：

- 原文文本
- 文件名
- `room`
- `wing`

所以 `wing` / `room` 的命名质量会明显影响召回结果。

混排后的每条结果大致包含：

```text
{
  text,
  wing,
  room,
  source_file,
  similarity,
  distance,
  rank_score,
  lexical_similarity,
  semantic_similarity,
  metadata,
  retrieval
}
```

## 3. 知识图谱支线

除了主检索库，MemPalace 还有一条并行的结构化事实存储：

- 文件: `mempalace/knowledge_graph.py`
- 后端: `SQLite`

它存的不是 chunk，而是时序三元组：

```text
Subject -> Predicate -> Object [valid_from -> valid_to]
```

示意：

```text
Kai  -> works_on    -> Orion           [2025-06-01 -> null]
Kai  -> recommended -> Clerk           [2026-01-15 -> null]
Maya -> assigned_to -> auth-migration  [2026-01-15 -> 2026-02-01]
```

对应表结构：

```text
entities
  - id
  - name
  - type
  - properties

triples
  - subject
  - predicate
  - object
  - valid_from
  - valid_to
  - confidence
  - source_closet
  - source_file
```

所以从架构上看，MemPalace 其实是两层：

```text
非结构化记忆:
  Chroma 原文 chunk 检索

结构化记忆:
  SQLite 时序知识图谱
```

## 4. 模型使用时的 L0-L3 记忆栈

`mempalace/layers.py` 又在上面包了一层面向模型的访问方式：

```text
L0: Identity
  读取 ~/.mempalace/identity.txt

L1: Essential Story
  从 palace 中挑高权重 / 重要 drawer
  拼成紧凑的 wake-up 文本

L2: On-Demand
  按 wing / room 直接取一小批相关记忆

L3: Deep Search
  走完整 hybrid search
```

图示：

```text
                 模型使用时的 4-layer stack

        ┌──────────────────────────────────┐
        │ L0 identity.txt                  │
        │ "我是谁，我服务谁，世界里有哪些人" │
        └──────────────────────────────────┘
                          +
        ┌──────────────────────────────────┐
        │ L1 essential story               │
        │ 从 palace 中抽最重要的一小批片段   │
        └──────────────────────────────────┘
                          +
        ┌──────────────────────────────────┐
        │ L2 on-demand recall              │
        │ 当前在聊某个 wing / room 时加载    │
        └──────────────────────────────────┘
                          +
        ┌──────────────────────────────────┐
        │ L3 deep search                   │
        │ 真正做全文 hybrid 检索            │
        └──────────────────────────────────┘
```

## 5. 最准确的一句话理解

如果只保留一句话，那就是：

```text
MemPalace =
  一个带 metadata 的本地 Chroma 检索库
  + 一个本地 SQLite 时序知识图谱
  + 一个面向 CLI / MCP / 模型的访问层
```

而不是：

```text
一个真的按 wing / room / drawer 逐层落盘的复杂专用数据库
```

`wing` / `room` / `drawer` 更像是它的语义模型和用户心智模型；
真正的实现核心还是：

- 原文 chunk 存储
- metadata 过滤
- hybrid retrieval
- 时间化知识图谱

## 6. 关键源码入口

如果之后要继续往下读源码，最值得先看的文件是：

- `mempalace/palace.py`
- `mempalace/backends/chroma.py`
- `mempalace/miner.py`
- `mempalace/convo_miner.py`
- `mempalace/normalize.py`
- `mempalace/searcher.py`
- `mempalace/knowledge_graph.py`
- `mempalace/layers.py`
- `mempalace/mcp_server.py`
