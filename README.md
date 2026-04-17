# Harness Workspace

这个目录是一个独立的 MemPalace 工作区，负责维护本地 palace、共享知识缓存，以及刷新相关脚本。

## 目录结构

```text
harness-workspace/
├── .mempalace_local/          # 本地 palace 数据
├── knowledges-cache/          # 可被挖掘的知识缓存
├── mempalace-github-code/     # MemPalace 源码副本
├── tools/                     # 同步、刷新、重建脚本
└── README.md
```

## 数据流

```text
source docs
-> tools/Sync-MemoryCache.ps1
-> knowledges-cache/
-> tools/Refresh-MemPalace.ps1
-> .mempalace_local/palace
```

## 核心目录说明

- `.mempalace_local/palace/`
  - 本地生成的向量库和知识图库数据。
  - 这是运行产物，不是人工编辑区。
- `knowledges-cache/`
  - MemPalace 挖掘的输入目录。
  - 每个 wing 目录下用 `mempalace.yaml` 定义配置。
  - `manual/` 放手工维护内容。
  - `generated/` 放同步脚本生成内容。
- `mempalace-github-code/`
  - MemPalace 源码和命令行入口所在目录。
- `tools/`
  - `sync-map.json` 定义同步映射。
  - `Sync-MemoryCache.ps1` 把源文档整理到 `knowledges-cache/`。
  - `Refresh-MemPalace.ps1` 挖掘各 wing 并刷新 palace。
  - `Rebuild-MemPalace.ps1` 删除旧 palace 后全量重建。

## 常用命令

在 `harness-workspace/` 目录下执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Sync-MemoryCache.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Refresh-MemPalace.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-MemPalace.ps1
```

## 维护约定

- 优先更新已有知识文件，不要随意创建 `v2`、`final_final` 之类副本。
- 需要长期维护的人工知识放到各 wing 的 `manual/`。
- 由脚本重新生成的内容放到各 wing 的 `generated/`。
- 不要把本地 `.mempalace_local/` 数据当成共享源；共享源应以 `knowledges-cache/` 下的 Markdown 为准。
