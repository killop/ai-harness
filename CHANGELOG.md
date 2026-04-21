# Changelog

本文件基于仓库 git 历史整理。

当前仓库尚未做正式版本标记，因此历史记录按日期归档；未提交的工作区改动归入 `Unreleased`。

## [Unreleased]

### 新增
- 新增 `harness-workspace/tools/mempalace_tools.py`，作为统一的跨平台入口，收敛 `setup`、`refresh`、`rebuild`、`start-mcp` 和 `daemon` 能力。
- 为受管 palace 增加蓝绿版本目录、`current.json` 指针、源文件快照和守护刷新机制，用于支持增量刷新与版本裁剪。

### 变更
- 将根目录和 `harness-workspace/` 文档重写为产品化说明，明确共享知识源、本地 palace、MCP 查询层和 daemon 刷新模型。
- 将 `.codex/config.toml` 的 MCP 启动方式切换为直接调用 Python + `mempalace_tools.py start-mcp`。
- 更新 `knowledges-cache/README.md`，把推荐操作改为 `daemon --run-once`，并说明蓝绿增量刷新行为。
- 调整 `mempalace/mcp_server.py`，在运行时从受管 palace 根目录解析 `current.json`，让 MCP 查询自动跟随当前 active 版本。

### 修复
- 在 `mempalace/mcp_server.py` 中重建 client / collection / KG 缓存，避免 palace 切换后继续绑定旧索引。
- 为 `mempalace/miner.py` 和 `mempalace/room_detector_local.py` 的 `mempalace.yaml` 读写显式指定 UTF-8 编码。

### 移除
- 删除旧的 PowerShell / `cmd` 包装脚本：`Setup-MemPalace.ps1`、`Refresh-MemPalace.ps1`、`Rebuild-MemPalace.ps1`、`Start-MemPalace-Mcp.cmd`。
- 删除基于 `sync-map.json` 的旧知识同步链路和 `.codex/start_mempalace_mcp.cmd` 启动脚本。

## [2026-04-20]

关联提交：`6e7d7e8`、`9c5cd83`、`21d9257`

### 新增
- 新增独立的 MemPalace 虚拟环境初始化脚本和 MCP 启动脚本，用于工作区本地运行。

### 变更
- 优化 `.codex/config.toml` 中的相对路径配置，降低启动命令对当前目录的依赖。
- 更新 `harness-workspace/README.md`，补充环境准备说明。

## [2026-04-17]

关联提交：`bf526c0`

### 新增
- 初始化 `ai-harness` 仓库，导入 `harness-workspace/`、知识缓存目录骨架和基础说明文档。
- 引入 `mempalace-github-code/` 源码副本以及配套插件、文档、测试和网站内容。
- 增加基于脚本的 `sync` / `refresh` / `rebuild` 工作流和初始 `.codex` MCP 启动配置。
