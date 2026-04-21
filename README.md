# Harness Workspace

`harness-workspace/` 是这个项目的本地记忆工作区。

它不是游戏运行时代码，也不是共享数据库，而是一套围绕 `MemPalace` 搭起来的“知识缓存 -> 本地 palace -> MCP 查询”产品化壳层。

它的目标很直接：

- 让团队把项目知识沉淀成 Markdown，而不是散落在对话、脑子和聊天记录里
- 让每个人都能从同一份共享知识源生成自己的本地 palace
- 让 MCP 在不打断正在使用的情况下，安全刷新到新版本
- 让刷新尽量增量化，而不是每次全量重建

---

## 1. 产品定位

这套东西的定位不是“文档仓库”，也不是“直接共享数据库”。

它更接近一个本地知识索引产品，分成两层：

- 共享层：团队维护 `knowledges-cache/` 里的 Markdown
- 本地层：每个人在自己的机器上生成 `.mempalace_local/palace/`

也就是说：

- 团队共享的是“知识源文件”
- 每个人本地拥有的是“索引产物”

这样做的原因是：

- 数据库文件不适合多人共享提交
- 本地 palace 可以按个人机器环境独立运行
- 本地 MCP 可以直接连本地 palace，查询快，风险低
- 刷新、回滚、切版本都可以只在本地完成

### 1.1 这个产品解决什么问题

- 项目知识分散，靠口口相传
- AI 工具每次都要重新读代码和文档，成本高
- 文档更新后，查询系统不能安全热切换
- Windows-only 的脚本体系太重，不利于跨平台运行

### 1.2 这个产品不做什么

- 不把 `.mempalace_local/` 当成团队共享产物
- 不直接改游戏运行时代码
- 不把所有外部目录做复杂同步编排
- 不试图做“中心化远程 palace 服务”

---

## 2. 产品总览

从产品视角看，可以把它理解成 4 个部件：

```text
+----------------------+      +----------------------+      +----------------------+
| Shared Knowledge     |      | Local Build Layer    |      | Query Layer          |
| Source               |      |                      |      |                      |
| knowledges-cache/    +----->+ mempalace_tools.py   +----->+ MCP / tools / agent  |
| Markdown + config    |      | refresh / daemon     |      | query active palace  |
+----------------------+      +----------------------+      +----------------------+
                                         |
                                         v
                              +----------------------+
                              | Local Palace         |
                              | .mempalace_local/    |
                              | versions + current   |
                              +----------------------+
```

你可以把它记成一句话：

```text
Markdown 是事实源
Palace 是本地索引
MCP 只读当前 active palace
refresh/daemon 负责把源变成新版本
```

---

## 3. 目录结构

```text
harness-workspace/
|-- .mempalace_local/          # 本地运行产物，不提交
|   |-- palace/
|   |   |-- current.json       # 当前 active 版本指针
|   |   |-- versions/          # 蓝绿版本目录
|   |   `-- ...                # chroma/sqlite/index 数据
|   `-- refresh-daemon/        # daemon 锁、日志、状态
|
|-- knowledges-cache/          # 团队共享知识源
|   |-- <wing>/
|   |   |-- mempalace.yaml     # wing 配置
|   |   |-- manual/            # 手写知识
|   |   `-- generated/         # 脚本生成知识
|   `-- README.md
|
|-- mempalace-github-code/     # MemPalace 源码副本
|
|-- tools/
|   `-- mempalace_tools.py     # 跨平台统一入口
|
`-- README.md
```

---

## 4. 核心概念

### 4.1 Wing

`wing` 是知识分区，不是物理数据库。

一个 wing 通常代表一个知识域，例如：

- `game_client`
- `game_server`
- `game_design`
- `game_shared`

每个 wing 目录下都有一个 `mempalace.yaml`，用于定义：

- wing 名称
- room 划分
- 关键词路由

### 4.2 Manual 和 Generated

- `manual/`：人手维护，优先放长期稳定、需要表达判断的知识
- `generated/`：脚本提炼出来的知识，适合大量同步型内容

这两类内容都会被挖掘进 palace，但维护方式不同。

### 4.3 Palace

`palace` 是本地索引库，不是共享源。

它里面保存的是：

- drawer / closet 等检索数据
- chroma / sqlite 等底层索引
- 当前 active 版本指针

所以 palace 的本质是“可再生缓存”。

### 4.4 Active Version

`current.json` 指向当前激活版本。

MCP 不直接绑定某个固定版本目录，而是读取：

```text
.mempalace_local/palace/current.json
```

然后跳到：

```text
.mempalace_local/palace/versions/<timestamp>
```

这就是蓝绿切换的基础。

---

## 5. 设计原则

### 5.1 共享源和本地产物分离

```text
team edits markdown
        |
        v
knowledges-cache/     <- shared, versioned, reviewable
        |
        v
.mempalace_local/     <- local, generated, disposable
```

这样可以让团队真正 review 的是知识本身，而不是二进制索引文件。

### 5.2 统一入口，全面 Python 化

这套工具只保留一个主入口：

```text
tools/mempalace_tools.py
```

所有常用动作都从这里进：

- `setup`
- `refresh`
- `rebuild`
- `start-mcp`
- `daemon`

这样做的好处：

- 跨平台
- 文件少
- 行为集中
- 文档和命令一致

### 5.3 蓝绿切换，而不是原地覆盖

如果 MCP 正在使用 palace，直接原地刷新有几个风险：

- 刷到一半被查询
- 文件锁冲突
- 索引状态不一致
- 刷新失败后没有回退点

所以这里采用蓝绿模型：

```text
active version A
      |
      | build new version
      v
candidate version B
      |
      | success
      v
current.json -> B
```

MCP 永远只读 active 版本，不读构建中的半成品。

### 5.4 增量优先，不无脑全量

最开始的蓝绿实现虽然安全，但每次都新建空版本，再全量 mine 所有 wing。

问题是：

- `file_already_mined` 的缓存只在“当前 palace 数据库”里有效
- 新版本如果是空的，就等于所有文件都第一次挖

现在改成了真正增量：

```text
old active palace
      |
      +--> copy to new version
               |
               +--> purge deleted files
               +--> reset changed-config wings
               +--> re-mine changed wings only
               |
               +--> current.json cutover
```

这样就同时满足：

- 查询安全
- 刷新可回退
- 未改的文件可以直接命中已有索引

---

## 6. 产品架构

### 6.1 逻辑架构图

```text
                         +----------------------+
                         | User / Agent         |
                         | asks memory question |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | MCP Server           |
                         | start-mcp            |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | current.json         |
                         | resolve active path  |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | active palace        |
                         | versions/<ts>        |
                         +----------------------+


Shared knowledge update path:

+----------------------+      +----------------------+      +----------------------+
| knowledges-cache/    | ---> | mempalace_tools.py   | ---> | new palace version   |
| markdown + yaml      |      | refresh / daemon     |      | candidate build      |
+----------------------+      +----------------------+      +----------------------+
                                                                      |
                                                                      v
                                                           +----------------------+
                                                           | current.json cutover |
                                                           +----------------------+
```

### 6.2 启动和查询关系

```text
python tools/mempalace_tools.py start-mcp
                |
                v
      mempalace.mcp_server --palace <logical root>
                |
                v
      read current.json
                |
                v
      attach active version
                |
                v
      serve queries
```

### 6.3 刷新关系

```text
refresh
  |
  +-- if unmanaged path:
  |      mine directly into target palace
  |
  `-- if managed root:
         run blue-green refresh
             |
             +-- compare source snapshot
             +-- if no change -> no-op
             +-- else build candidate version
             +-- cutover current.json
```

---

## 7. 刷新设计

### 7.1 为什么需要 daemon

`refresh` 适合手动触发。

`daemon` 适合常驻监听 `knowledges-cache/`，在文件变化后自动刷新。

它的职责非常克制：

- 只看 `knowledges-cache/*`
- 只做快照对比
- 只做去抖和触发刷新
- 不负责复杂跨目录同步编排

### 7.2 Daemon 工作方式

```text
loop every N seconds
    |
    +-- scan knowledges-cache snapshot
    |
    +-- diff with previous snapshot
    |
    +-- if changed:
    |      record pending changes
    |      reset debounce timer
    |
    `-- if debounce elapsed:
           run blue-green incremental refresh
```

### 7.3 蓝绿增量刷新流程

```text
1. read active palace
2. load previous source_snapshot.json
3. scan current knowledges-cache
4. compute changed files / changed wings
5. if nothing changed:
      keep current active version
6. else:
      copy active palace -> candidate version
      purge deleted files
      reset wings whose mempalace.yaml changed
      re-mine changed wings only
      write candidate source_snapshot.json
      update current.json
      prune old versions
```

### 7.4 哪些情况会触发什么行为

| 变化类型 | 行为 |
| --- | --- |
| 某个 Markdown 改了 | 只重挖所属 wing |
| 某个 Markdown 删除了 | 先 purge 旧 drawer，再重挖该 wing |
| `mempalace.yaml` 改了 | 整个 wing reset，再全量重挖该 wing |
| 没有变化 | 直接 no-op |
| 第一次没有快照 | 做一次 full refresh 建基线 |

### 7.5 为什么现在 refresh 会很快

如果日志出现：

```text
No knowledge changes detected. Keeping current active palace.
```

说明：

- 当前知识源和上次快照一致
- 没有进入真实 mine
- 也没有新建候选版本

这是预期行为，不是异常。

---

## 8. 数据流

### 8.1 从知识源到可查询记忆

```text
author writes markdown
        |
        v
knowledges-cache/<wing>/
        |
        v
mempalace_tools.py refresh / daemon
        |
        v
MemPalace mine
        |
        v
palace versions/<timestamp>
        |
        v
current.json points to active version
        |
        v
MCP query reads active version
```

### 8.2 团队协作模型

```text
                +----------------------+
                | Git repository       |
                | knowledges-cache/    |
                +----------+-----------+
                           |
        +------------------+------------------+
        |                                     |
        v                                     v
+----------------------+           +----------------------+
| Developer A          |           | Developer B          |
| local palace A       |           | local palace B       |
| .mempalace_local/    |           | .mempalace_local/    |
+----------------------+           +----------------------+
        |                                     |
        v                                     v
   local MCP A                           local MCP B
```

重点是：

- 大家共享同一份知识源
- 但每个人都构建自己的本地索引

---

## 9. 核心目录说明

### 9.1 `.mempalace_local/palace/`

- 本地生成的 palace 数据目录
- `current.json` 指向 active version
- `versions/` 保存历史版本
- `source_snapshot.json` 记录上次构建对应的源文件快照
- 这是运行产物，不是人工编辑区

### 9.2 `.mempalace_local/refresh-daemon/`

- `daemon.lock`：防止同一工作区启动多个 daemon
- `daemon.log`：守护进程日志
- `state.json`：当前快照状态、pending 数量、最近刷新状态

### 9.3 `knowledges-cache/`

- 这是团队共享事实源
- 每个 wing 是一个知识域
- `mempalace.yaml` 决定这个 wing 怎么被 mine
- `manual/` 适合手工沉淀知识
- `generated/` 适合脚本生成知识

### 9.4 `mempalace-github-code/`

- MemPalace 源码副本
- `setup` 会在这里创建 `.venv`
- `start-mcp` 和 `refresh` 最终都依赖这里的 Python 环境和 CLI

### 9.5 `tools/mempalace_tools.py`

这是整个产品的控制台入口。

你可以把它理解成：

```text
operator shell
      |
      v
mempalace_tools.py
      |
      +-- setup
      +-- refresh
      +-- rebuild
      +-- start-mcp
      `-- daemon
```

---

## 10. 常用命令

在 `harness-workspace/` 目录下执行。

### 10.1 安装和初始化

macOS / Linux:

```bash
python3 ./tools/mempalace_tools.py setup
```

Windows:

```powershell
python .\tools\mempalace_tools.py setup
```

作用：

- 创建专用虚拟环境
- 安装 MemPalace 依赖
- 校验 MCP 依赖能否正常导入

### 10.2 手动刷新

macOS / Linux:

```bash
python3 ./tools/mempalace_tools.py refresh
```

Windows:

```powershell
python .\tools\mempalace_tools.py refresh
```

作用：

- 如果是 managed root，就走蓝绿增量刷新
- 如果没有变化，会直接 no-op

### 10.3 全量重建

```bash
python3 ./tools/mempalace_tools.py rebuild
```

适合：

- 你明确要重建一个非托管 palace
- 需要验证从零开始的构建链路

不适合：

- 日常在线刷新

### 10.4 启动 MCP

```bash
python3 ./tools/mempalace_tools.py start-mcp
```

作用：

- 启动本地 MemPalace MCP server
- 让查询跟随 `current.json` 指向的 active version

### 10.5 启动守护进程

```bash
python3 ./tools/mempalace_tools.py daemon
```

常用参数：

```bash
python3 ./tools/mempalace_tools.py daemon --debounce-seconds 3 --keep-versions 3
```

### 10.6 只跑一次守护刷新

```bash
python3 ./tools/mempalace_tools.py daemon --run-once
```

适合：

- 手动验证刷新链路
- CI 或临时操作
- 不想常驻 daemon

---

## 11. 推荐使用方式

### 11.1 新机器首次接入

```text
git pull
   |
   v
python tools/mempalace_tools.py setup
   |
   v
python tools/mempalace_tools.py daemon --run-once
   |
   v
python tools/mempalace_tools.py start-mcp
```

### 11.2 日常写知识

```text
edit markdown under knowledges-cache/
        |
        v
run refresh or let daemon detect it
        |
        v
query through MCP
```

### 11.3 推荐工作流

#### 模式 A：手动模式

适合低频更新。

```text
改文档 -> refresh -> 查询
```

#### 模式 B：守护模式

适合你持续维护知识源。

```text
开 daemon 常驻
    |
    +-- 改文档
    +-- 等去抖
    `-- 自动刷新
```

---

## 12. 典型场景

### 12.1 项目知识沉淀

把一次需求理解、方案总结、排错经验放进 `manual/`，让后续 agent 和开发都能查询。

### 12.2 自动知识编译

把脚本分析、设计文档提炼、代码结构总结放进 `generated/`，作为可再生知识层。

### 12.3 本地 AI 查询

通过 MCP 直接问：

- 这个系统入口在哪
- 某个模块依赖谁
- 某类逻辑通常放在哪

---

## 13. 关键设计取舍

### 13.1 为什么不共享 palace 数据库

因为它不适合做代码评审和多人协作源。

共享数据库的问题：

- 二进制不可读
- 冲突难处理
- 不同平台和环境容易不一致
- 很难看出“知识到底改了什么”

### 13.2 为什么不原地 refresh

因为在线查询时不够安全。

原地刷新意味着：

- 构建中的状态可能被读到
- 索引中间态可能暴露
- 出错时难回退

### 13.3 为什么只监听当前文件夹

因为产品边界需要稳定。

这套工作区现在刻意不做“全仓库复杂同步编排”，而是只对 `knowledges-cache/` 负责。

优点是：

- 行为简单
- 可解释
- 变更边界清楚
- 出问题时容易排查

---

## 14. 故障排查

### 14.1 `refresh` 没反应

先看你改的是不是：

```text
harness-workspace/knowledges-cache/
```

如果你改的是项目别的目录，`refresh` 不会理它。

### 14.2 `refresh` 很快结束

如果日志是：

```text
No knowledge changes detected. Keeping current active palace.
```

说明没有检测到知识源变化，属于正常。

### 14.3 `refresh` 很慢

重点看是不是以下情况：

- 第一次建立基线
- `mempalace.yaml` 改了，导致整 wing reset
- `seed copy` 失败，回退成 full refresh
- 本次真的有大 wing 发生改动

### 14.4 daemon 启动失败

检查：

- 有没有旧 daemon 还活着
- `.mempalace_local/refresh-daemon/daemon.lock` 是否残留
- `state.json` 里的 pid 是否还存在

### 14.5 MCP 启动失败

检查：

- 是否先跑过 `setup`
- `.codex/config.toml` 里 Python 和 `mempalace_tools.py` 路径是否有效
- `mempalace-github-code/.venv` 是否存在

---

## 15. 维护约定

- 优先更新已有知识文件，不要随意创建 `v2`、`final_final` 一类副本
- 需要长期维护的人工知识放到各 wing 的 `manual/`
- 由脚本重新生成的内容放到各 wing 的 `generated/`
- 不要手改 `.mempalace_local/` 下的数据库和索引文件
- 不要把本地 `.mempalace_local/` 当成共享源提交
- 团队共享的事实源应始终是 `knowledges-cache/` 下的 Markdown

---

## 16. 一句话总结

```text
Harness Workspace = 用共享 Markdown 做事实源，
在本地生成可蓝绿切换、可增量刷新、可被 MCP 查询的项目记忆工作区。
```
