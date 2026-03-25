<div align="center">

# TreeSeek

### 面向长文档的结构化检索工具

**结构树解析 · 本地混合索引 · 连续查询 · 可解释结果**

<p>
  <a href="#快速开始">快速开始</a> ·
  <a href="#核心能力">核心能力</a> ·
  <a href="#适用场景">适用场景</a> ·
  <a href="#商业价值">商业价值</a> ·
  <a href="#配置模板">配置模板</a>
</p>

</div>

---

## 项目简介

TreeSeek 是一个面向 **长 PDF / Markdown 文档** 的结构化检索工具，适合需要反复查询专业文档、并且希望结果**可追溯、可解释、可本地部署**的场景。

它的核心思路不是把文档简单切块后做黑盒相似度搜索，而是：

1. 从文档中抽取可解释的层级结构
2. 在结构树上建立本地查询索引
3. 返回带标题、页码区间、命中片段和解释信息的结果

> TreeSeek 是基于开源项目 [PageIndex](https://github.com/VectifyAI/PageIndex) 的下游重构与工程增强版本。  
> 我们保留了“长文档结构树”的核心思想，但重新整理了对外品牌、包结构、CLI、README、运行控制和检索能力，使其更适合工程化落地与持续演进。

---

## 为什么是 TreeSeek

很多长文档检索系统的问题在于：

- 只做向量相似度，找得到“相近内容”，找不到“正确章节”
- 结果不带结构信息，很难回溯来源
- 文档一长就反复重解析，查询成本高
- 一旦模型服务有限流，整个流程不稳定

TreeSeek 试图解决的正是这些问题。

它更偏向：

- **结构优先**
- **本地索引优先**
- **连续查询优先**
- **结果解释优先**

---

## 核心能力

| 能力 | 说明 |
| --- | --- |
| PDF 结构树解析 | 从 PDF 中提取章节树、页码区间、可选摘要 |
| Markdown 结构树解析 | 基于标题层级生成结构树 |
| Word 结构树解析 | 支持 `.docx` / `.docm`，基于 Word Heading 样式构建章节树 |
| 本地查询索引 | 在结构树上构建可复用索引，支持 build once, query many times |
| 混合检索 | 倒排索引 + BM25-lite + phrase/proximity + diversity |
| 结果片段返回 | 输出 `snippet`、`highlight_terms`、`snippet_field` |
| Explain 模式 | 输出 `field_scores`、`bonuses_applied`、`phrase_matches` |
| Query-only 模式 | 使用 `--index-path` 直接查询，无需重复解析源文档 |
| 运行时稳态控制 | 支持并发限制、RPM 限制、重试退避、调试日志开关 |
| 可选 LLM rerank | 在本地召回结果基础上再做模型重排序 |

---

## 适用场景

| 场景 | 典型文档 | 适合原因 |
| --- | --- | --- |
| 财报与投研分析 | 年报、季报、招股书、业绩会材料 | 文档结构强，章节长，页码证据重要 |
| 法律与合规检索 | 合同、法规、制度、审计手册 | 条款层级清晰，需要可追溯定位 |
| 技术文档问答 | API 文档、部署手册、架构说明、Runbook | 标题结构稳定，适合反复查询 |
| 企业知识库 | SOP、FAQ、培训文档、制度文件 | 支持 build once, query many times |
| 制造与设备运维 | 设备手册、保养指南、故障处理文档 | 页码、步骤、表格、章节都很关键 |
| 政策与公共治理 | 政策文件、标准规范、公文、报告 | 长文档检索需要结构化与解释性 |

---

## 商业价值

| 价值方向 | 实际收益 |
| --- | --- |
| 降低人工检索成本 | 从“翻 PDF 找内容”变成“建树后持续查询” |
| 提高答案可追溯性 | 每个结果都能带标题、页码范围、片段 |
| 更适合私有部署 | 核心流程不依赖外部向量库 |
| 提高重复查询效率 | 建一次索引，后续直接 query-only |
| 便于调试与迭代 | explain 字段和运行时限流帮助快速排查问题 |
| 更适合垂直行业落地 | 财报、法律、运维、政务等长文档场景收益明显 |

---

## 项目结构

```text
treeseek/
  __init__.py
  config.yaml
  pdf_tree.py
  markdown_tree.py
  utils.py
  indexing/
    builder.py
    filters.py
    llm_rerank.py
    models.py
    normalizer.py
    postings.py
    query_engine.py
    scoring.py
    snippets.py
    storage.py
run_treeseek.py
docs/
scripts/
tests/
```

---

## 安装

```bash
python -m pip install -r requirements.txt
```

说明：

- 项目使用 `LiteLLM` 作为统一模型调用层
- `pyroaring` 已包含在依赖中，用于 bitmap postings 加速
- 默认适配 OpenAI-compatible 服务

---

## 配置模板

请使用 [`.env.example`](.env.example) 作为模板。

推荐流程：

1. 复制 `.env.example` 为 `.env`
2. 填写以下最小配置：
   - `MODEL`
   - `API_KEY`
   - `API_URL`
3. 如 provider 有严格限流，再按需调整：
   - `TREESEEK_LLM_MAX_CONCURRENCY`
   - `TREESEEK_LLM_MAX_RPM`
   - `TREESEEK_LLM_RETRY_BASE_DELAY`
   - `TREESEEK_LLM_RETRY_MAX_DELAY`

> 如果你使用的是 OpenAI-compatible 服务并传入服务端原生模型 ID，TreeSeek 会自动兼容 LiteLLM 所需的 provider 前缀。

---

## 快速开始

### 1. 解析 PDF

```bash
python run_treeseek.py --pdf_path /path/to/document.pdf
```

### 2. 解析 Markdown

```bash
python run_treeseek.py --md_path /path/to/document.md --if-add-node-summary no
```

### 3. 解析 Word 文档

```bash
python run_treeseek.py --docx_path /path/to/document.docx --if-add-node-summary no
```

### 4. 建索引并立即查询

```bash
python run_treeseek.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --include-text yes \
  --query "retrieval design" \
  --top-k 5
```

### 5. 建一次索引，后续持续查询

第一次构建索引：

```bash
python run_treeseek.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --include-text yes
```

后续直接复用索引：

```bash
python run_treeseek.py \
  --index-path results/document_query_index.pkl.gz \
  --query "retrieval design" \
  --top-k 5
```

### 6. 开启 Explain 模式

```bash
python run_treeseek.py \
  --index-path results/document_query_index.pkl.gz \
  --query "\"retrieval design\"" \
  --top-k 5 \
  --debug-explain yes
```

### 7. 运行 benchmark

```bash
python scripts/benchmark_query_index.py \
  --structure-path tests/results/2023-annual-report_structure.json \
  --query "financial stability" \
  --query "supervisory developments"
```

---

## Python API

```python
from treeseek import (
    build_pdf_tree,
    build_markdown_tree,
    build_query_index,
    search_index,
    rerank_query_results,
)
```

主要入口：

- `build_pdf_tree(...)`
- `build_markdown_tree(...)`
- `build_query_index(...)`
- `search_index(...)`
- `rerank_query_results(...)`

---

## 查询输出

默认查询结果包含：

- `node_id`
- `title`
- `start_index`
- `end_index`
- `score`
- `matched_terms`
- `matched_fields`
- `ancestor_ids`
- `snippet`
- `highlight_terms`
- `snippet_field`

开启 `--debug-explain yes` 后，还会额外返回：

- `field_scores`
- `bonuses_applied`
- `phrase_matches`

---

## 运行时控制

TreeSeek 提供了比较完整的运行控制参数，适合在限流严格的模型服务上稳定运行：

- `TREESEEK_LLM_MAX_CONCURRENCY`
- `TREESEEK_LLM_MAX_RPM`
- `TREESEEK_LLM_RETRY_BASE_DELAY`
- `TREESEEK_LLM_RETRY_MAX_DELAY`
- `TREESEEK_DEBUG_LOGS`

这对于：

- 并发受限
- RPM 严格
- 长文档递归切分
- 持续排查 provider 问题

都非常有帮助。

---

## 测试

推荐离线回归：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_normalizer.py \
  tests/test_postings.py \
  tests/test_index_builder.py \
  tests/test_query_engine.py \
  tests/test_storage.py \
  tests/test_cli.py \
  tests/test_snippets.py \
  tests/test_pdf_recursive_split.py \
  tests/test_scoring_bm25.py \
  tests/test_phrase_proximity.py \
  tests/test_result_diversity.py \
  -q -p no:cacheprovider
```

可选在线 LLM 冒烟测试：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_llm_rerank_live.py \
  -q -p no:cacheprovider -m live_llm
```

---

## 文档

- [Architecture](docs/architecture.md)
- [Enhancement Roadmap](docs/rag_enhancement_roadmap.md)

---

## 来源与许可证

TreeSeek 基于开源项目 PageIndex 的代码与思路进行下游重构，保留明确来源说明，并尊重上游许可证。

- 上游项目：`VectifyAI/PageIndex`
- 当前目标：将其演进为更适合工程落地的长文档结构化检索工具

详见：

- `LICENSE`
- `NOTICE.md`
