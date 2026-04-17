# MemPalace 与 Memory-Palace-Openclaw 对比纪要

本文整理当前仓库 `E:\github\mempalace` 与 `E:\github\Memory-Palace-Openclaw` 的关键差异，重点覆盖：

- `embedding` 和 `reranker` 的概念区别
- 当前 `mempalace` 的检索现状
- Openclaw 的 `rerank` 和 `visual memory` 能力
- Openclaw 的 `intent analysis / intent routing` 能力
- 两个仓库在文本记忆、视觉记忆、OCR、视觉检索、重排、前端上的差异

## 1. 概念解释

### 1.1 Embedding 是什么

`embedding` 可以理解成“先把文本变成向量坐标，再按语义相似度召回候选”。

它解决的问题是：

- 先把可能相关的内容捞出来
- 即使查询和原文措辞不同，也有机会召回

如果正确答案根本没有被召回出来，后面的排序再强也救不回来。

### 1.2 Reranker 是什么

`reranker` 可以理解成“第二阶段精排”。

它通常不看全库，而是只看：

- 用户问题
- 第一阶段召回出来的前若干条候选

然后给这些候选重新打更细的相关性分，再重新排序。

它解决的问题是：

- 正确答案已经进了候选池
- 但没排在最前面

一句话区分：

- `embedding` 决定“能不能把对的东西捞上来”
- `reranker` 决定“捞上来以后能不能排得更靠前”

## 2. 当前 mempalace 的检索现状

当前公开仓库里的 `mempalace` 没有 Openclaw 那种独立的 reranker 模型接入路径。现在实际运行的是：

- Chroma 向量召回
- lexical / BM25 风格词法打分
- `closet_boost`
- 最终 hybrid 排序

主要实现位置：

- `mempalace/searcher.py`
- `mempalace/backends/chroma.py`

其中：

- 排序逻辑在 `mempalace/searcher.py:190`
- drawer 搜索主流程在 `mempalace/searcher.py:560`
- 最终又会结合 `closet_boost` 再排一次

当前仓库默认也没有显式指定 embedding function，而是直接使用 Chroma 默认 embedding function。根据本机安装的 `chromadb 1.5.2` 源码，默认实现是：

- `DefaultEmbeddingFunction`
- 实际委托到 `ONNXMiniLM_L6_V2`

相关位置：

- 当前仓库：`mempalace/backends/chroma.py:126`
- 本机 Chroma 源码：`E:\Programs\Python\Python313\Lib\site-packages\chromadb\api\types.py:946`

另外，README 里提到的：

- `Hybrid + Haiku rerank = 100%`

这条结果在公开 README 中存在，但 README 也明确说明公开 benchmark 脚本里还没有把这条 rerank pipeline 放出来。

相关位置：

- `README.md:66`
- `README.md:571`

## 3. Openclaw 的 rerank 是怎么做的

Openclaw 的 `rerank` 是独立的第二阶段重排，而不是简单的本地 BM25 混排。

它的大致流程是：

1. 先做混合召回，得到一批 candidate
2. 对 candidate 先算基础分 `base_score`
3. 挑出可 rerank 的候选，按 memory 或 chunk 分组
4. 把这些候选文本发给外部 reranker API
5. 得到 `rerank_score`
6. 按权重混回总分

核心公式：

- `final_score = base_score + rerank_weight * rerank_score`

关键实现位置：

- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client_retrieval.py:194`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client_retrieval.py:276`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client_retrieval.py:296`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:3152`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:7806`

Openclaw 的 reranker 支持：

- primary / small-batch / fallback 路由
- OpenAI-compatible `/rerank`
- Cohere 风格 `/rerank`
- LM Studio chat / responses 兼容路径

相关位置：

- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2709`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2754`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2884`

## 4. Openclaw 的 rerank 提升大不大

结论不能简单说“稳定提升”。

从仓库里已经写出的 benchmark 看：

- 在一组 20-query eval set 上，`MP-C -> MP-D` 的提升明显
- 但在主 18-scenario small corpus 上，`C -> D` 的 MRR 反而下降

主 corpus 文档里的原始结果：

- `MP Profile C`: `HR=0.944, MRR=0.922`
- `MP Profile D`: `HR=0.944, MRR=0.894`

仓库自己给出的表述是：

- `reranker did not stably demonstrate advantage at this scale`

相关位置：

- `E:\github\Memory-Palace-Openclaw\backend\tests\benchmark\E2E_BLACKBOX_SPEC.md:292`
- `E:\github\Memory-Palace-Openclaw\backend\tests\benchmark\E2E_BLACKBOX_SPEC.md:293`
- `E:\github\Memory-Palace-Openclaw\backend\tests\benchmark\E2E_BLACKBOX_SPEC.md:298`

但它也在另一处 benchmark 里说明：

- `SC12` 的 scale stress 只有 D 通过

这说明 rerank 更可能在“候选池更大、更嘈杂、更难排”的场景下有价值，而不是在小而干净的数据集上稳定普涨。

相关位置：

- `E:\github\Memory-Palace-Openclaw\backend\tests\benchmark\E2E_BLACKBOX_SPEC.md:190`

## 5. Openclaw 是否支持视觉

支持，但要说准确：

- 它支持的是 `visual memory`
- 不等于“所有图片自动长期入库”
- 也不等于“完整原生多模态大模型记忆系统”

它的产品面里已经有正式的视觉能力：

- `memory_store_visual` 已是正式能力
- 文档明确说 `visual memory` 已在当前产品面成立

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\00-IMPLEMENTED_CAPABILITIES.md:34`
- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\00-IMPLEMENTED_CAPABILITIES.md:38`

### 5.1 Openclaw 的视觉能力具体包含什么

Openclaw 有单独的 visual memory 写入工具和数据结构。

显式工具：

- `memory_store_visual`

CLI 参数可以直接收：

- `mediaRef`
- `summary`
- `ocr`
- `scene`
- `whyRelevant`
- `entities`

相关位置：

- `E:\github\Memory-Palace-Openclaw\extensions\memory-palace\src\cli-store-visual.ts:31`

它写入的内容不是普通文本块，而是结构化的 visual memory 记录，字段包括：

- `Visual Memory`
- `media_ref`
- `summary`
- `ocr`
- `entities`
- `scene`
- `why_relevant`

相关位置：

- `E:\github\Memory-Palace-Openclaw\extensions\memory-palace\src\visual-render-search.ts:232`

它还支持 visual enrichment：

- 可配置 OCR provider
- 可配置 analyzer provider
- 可决定是否存 `ocr / entities / scene / whyRelevant`

相关位置：

- `E:\github\Memory-Palace-Openclaw\extensions\memory-palace\src\config.ts:648`
- `E:\github\Memory-Palace-Openclaw\extensions\memory-palace\src\visual-memory.ts:375`

### 5.2 Openclaw 的视觉检索能力是什么形态

Openclaw 更准确的说法是：

- 它支持“视觉记忆的存储与检索”
- 检索依赖 `media_ref + OCR + summary + entities + visual hash`

文档里对 visual memory 的写入保护直接写了：

- `visual memory：优先走 visual hash 快路`

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\25-MEMORY_ARCHITECTURE_AND_PROFILES.md:286`

它还带了 visual benchmark，里面有：

- `ocr_exact`
- `search_hit_at_3_rate`

说明至少有针对 OCR token 命中率的真实检索验证。

相关位置：

- `E:\github\Memory-Palace-Openclaw\scripts\openclaw_visual_memory_benchmark.py:589`
- `E:\github\Memory-Palace-Openclaw\scripts\openclaw_visual_memory_benchmark.py:1318`

### 5.3 重要边界

Openclaw 文档明确写了：

- visual memory 默认会 auto-harvest
- 默认不会自动长期存库
- 真正长期存图仍然需要显式 `memory_store_visual`

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\02-SKILLS_AND_MCP.md:146`
- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\02-SKILLS_AND_MCP.md:424`

## 6. 当前 mempalace 是否支持视觉

按当前公开代码，可以认为：

- 不支持 visual memory
- 不支持图片入库
- 不支持 OCR pipeline
- 不支持图片检索

证据很直接：

### 6.1 Conversation 扫描阶段就不收图片

它只扫描：

- `.txt`
- `.md`
- `.json`
- `.jsonl`

相关位置：

- `mempalace/convo_miner.py:48`

测试也明确写了：

- `.png` 不会被纳入扫描结果

相关位置：

- `tests/test_convo_miner_unit.py:85`

### 6.2 就算聊天记录里有 image block，也会被丢掉

测试里有一条：

- 输入块里既有 `text` 也有 `image`
- 最终只保留文本 `"hello"`

相关位置：

- `tests/test_normalize.py:90`

所以当前 `mempalace` 的能力边界仍然是：

- 文本记忆系统
- 不是视觉记忆系统

## 7. Skill / 用法层 对比

这里需要一个重要修正：

- 不能简单说当前 `mempalace` “没有 skill”
- 更准确的说法是：`mempalace` 有官方 skill / 指令集成，但没有 Openclaw 那种“plugin + bundled skills + WebUI 技能页”的产品化 skill 架构

### 7.1 Openclaw 的 skill 是什么形态

Openclaw 文档对这层定义得非常明确：

- `plugin` 是接线层
- `skills` 是用法层
- `backend` 是发动机

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\25-MEMORY_ARCHITECTURE_AND_PROFILES.md:22`
- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\25-MEMORY_ARCHITECTURE_AND_PROFILES.md:154`

它还明确把自己描述成：

- `OpenClaw plugin + bundled skills`

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\TECHNICAL_OVERVIEW.md:13`

而且这套 skill 不是只存在于仓库文档里，还包括：

- `docs/skills/` 下的 canonical skill 文档
- 安装脚本
- 同步脚本
- WebUI 里的 `Skills` 条目和详情面板

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\skills\SKILLS_QUICKSTART.md:20`
- `E:\github\Memory-Palace-Openclaw\scripts\install_skill.py:43`
- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\15-END_USER_INSTALL_AND_USAGE.md:55`
- `E:\github\Memory-Palace-Openclaw\docs\openclaw-doc\15-END_USER_INSTALL_AND_USAGE.md:80`

所以 Openclaw 的 skill 不是“顺手给了一个 SKILL.md”，而是产品用法层的一部分。

### 7.2 当前 mempalace 的 skill 是什么形态

当前 `mempalace` 其实也有官方 skill 集成，只是组织方式和 Openclaw 不同。

证据包括：

- 仓库里直接有 OpenClaw skill 文件：`integrations/openclaw/SKILL.md`
- 官方文档明确写了 “MemPalace provides an official skill for OpenClaw”
- Claude Code 指南里也明确让用户通过 `/skills` 验证 `mempalace` 是否出现
- CLI 里还有 `mempalace instructions ...`，专门输出 skill instructions

相关位置：

- `E:\github\mempalace\integrations\openclaw\SKILL.md:1`
- `E:\github\mempalace\website\guide\openclaw.md:1`
- `E:\github\mempalace\website\guide\claude-code.md:12`
- `E:\github\mempalace\mempalace\cli.py:271`
- `E:\github\mempalace\mempalace\instructions\mine.md:1`

所以更准确的比较应该是：

- `mempalace`：有 skill / instruction 集成能力
- `Openclaw`：把 skill 进一步做成了 bundled skills、安装链路、WebUI 可见条目和产品用法层

## 8. 意图分析 / intent routing 对比

结论先说：

- Openclaw 支持意图分析
- 而且不是停留在提示词层，而是实际接进了检索路由
- 当前 `mempalace` 没看到同等级的内建 intent classifier + strategy routing 实现

### 8.1 Openclaw 是怎么做的

Openclaw 里有两条意图分析路径：

- 默认内建的关键词 / 规则分类器
- 可选的实验性 `INTENT_LLM_*` 路径

默认分类器对应的核心实现就是：

- `classify_intent`

支持的核心意图类型包括：

- `factual`
- `exploratory`
- `temporal`
- `causal`

冲突或低信号时还会回退：

- `unknown`

它不是只分个类就结束，而是会继续映射到检索策略模板：

- `factual` → `factual_high_precision`
- `exploratory` → `exploratory_high_recall`
- `temporal` → `temporal_time_filtered`
- `causal` → `causal_wide_pool`

相关位置：

- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2225`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2410`
- `E:\github\Memory-Palace-Openclaw\docs\TECHNICAL_OVERVIEW.md:399`
- `E:\github\Memory-Palace-Openclaw\docs\TOOLS.md:350`

### 8.2 它会不会真的影响检索行为

会。

Openclaw 的 `intent_profile` 会进入 advanced retrieval，然后改动候选池大小和 hybrid 各分量权重。例如：

- `factual` 会缩小 candidate multiplier，偏高精度
- `exploratory` 会放大 candidate multiplier，偏高召回
- `temporal` 会提高 recency 权重
- `causal` 会扩大候选池，偏因果排查

这说明它不是“解释一下用户问题类型”，而是实打实地参与检索路由。

相关位置：

- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:6922`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:7650`

### 8.3 LLM 版意图分析是默认开的吗

不是。

当前仓库公开配置里默认是：

- `INTENT_LLM_ENABLED=false`

也就是说默认先走内建关键词规则分类；只有你显式开启 `INTENT_LLM_*`，它才会优先尝试 LLM 分类。并且就算开启了：

- 配置缺失会回退
- 请求失败会回退
- 返回空结果会回退
- JSON 非法会回退
- 意图标签非法也会回退

所以 Openclaw 的设计是：

- 默认有意图分析
- 默认不依赖 LLM
- LLM 只是可选增强

相关位置：

- `E:\github\Memory-Palace-Openclaw\.env.example:59`
- `E:\github\Memory-Palace-Openclaw\backend\db\sqlite_client.py:2420`
- `E:\github\Memory-Palace-Openclaw\docs\DEPLOYMENT_PROFILES.md:298`
- `E:\github\Memory-Palace-Openclaw\docs\DEPLOYMENT_PROFILES.md:337`
- `E:\github\Memory-Palace-Openclaw\docs\TECHNICAL_OVERVIEW.md:414`

### 8.4 LLM 版会稳定更好吗

也不能简单说“肯定更好”。

仓库自己的评测里写得比较明确：

- `keyword_scoring_v2` 在 basic gold set 上到过 `1.000`
- product gold set 上 rule-based 也已经有 `0.910`
- LLM 路径对 `temporal / causal` 有提升潜力
- 但也会把一部分 `factual` 误判成 `exploratory`

所以更准确的结论是：

- Openclaw 支持 LLM intent enhancement
- 但当前仓库证据并不支持“LLM intent 一定全面优于规则版”

相关位置：

- `E:\github\Memory-Palace-Openclaw\docs\EVALUATION.md:475`
- `E:\github\Memory-Palace-Openclaw\docs\EVALUATION.md:517`
- `E:\github\Memory-Palace-Openclaw\docs\EVALUATION.md:624`
- `E:\github\Memory-Palace-Openclaw\docs\EVALUATION.md:630`

### 8.5 当前 mempalace 对应到哪一层

当前 `mempalace` 里能看到两类相关东西：

- `query_sanitizer.py` 会从被系统提示词污染的长 query 里抽出真正搜索句子
- `instructions/search.md` 会让上层 agent 在使用时“提取 search intent”

但这两者更接近：

- 查询净化
- 提示词层指导

而不是 Openclaw 那种：

- 内建 intent classifier
- 输出 `intent_profile`
- 再驱动不同 retrieval strategy template

目前公开代码里我没有看到 `mempalace` 存在 Openclaw 同等级的 `intent -> strategy routing` 检索实现。

相关位置：

- `E:\github\mempalace\mempalace\query_sanitizer.py:39`
- `E:\github\mempalace\mempalace\mcp_server.py:415`
- `E:\github\mempalace\mempalace\instructions\search.md:7`

## 9. 总对照

| 维度 | Memory-Palace-Openclaw | 当前 mempalace |
|---|---|---|
| 文本记忆 | 有，正式产品能力 | 有，核心主能力 |
| 图片长期存储 | 有，`memory_store_visual` | 没有公开链路 |
| OCR | 有，可配 enrichment/OCR provider | 没有公开 OCR pipeline |
| 视觉检索 | 有，依赖 OCR/summary/entities/visual hash | 没有 |
| 独立 reranker | 有，第二阶段 API rerank | 没有公开独立 reranker |
| 当前默认排序 | 混合召回 + rerank + 可选 MMR | 向量 + lexical/BM25 + closet_boost |
| 意图分析 / 检索路由 | 有，默认规则分类，可选 `INTENT_LLM_*` 增强，并实际改动检索策略 | 没看到同等级的内建 intent routing；当前更像 query sanitize + instruction guidance |
| Skill / 用法层 | 有，plugin-bundled skills，且 WebUI 可见 | 有官方 skill / instruction 集成，但不是同等产品化 skill 架构 |
| Dashboard / 前端 | 有，产品级 dashboard，可看 visual branch | 没有产品级 dashboard；当前主入口是 CLI |

## 10. 最终结论

如果只看“当前公开代码”：

- `mempalace` 更像本地文本记忆引擎
- `Memory-Palace-Openclaw` 更像产品化的记忆插件系统
- 两边都不是“完全没 skill / 只有一边有 skill”这么简单
- 更准确的差别在于：Openclaw 把 `skill` 做成了产品结构的一层，而 `mempalace` 目前更像提供 skill 集成入口和官方接线件

如果只看你之前关心的三个点：

- `rerank`：Openclaw 明显更完整，但提升不是稳定普涨
- `视觉`：Openclaw 有正式 visual memory；当前 `mempalace` 没有
- `意图分析`：Openclaw 支持，而且已经接进检索路由；当前 `mempalace` 还没有看到同等级实现
