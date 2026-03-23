# RAG

一个结构化文档检索工具包，用于把长 PDF 或 Markdown 文档转换为层级树，并构建可查询的混合索引。

> 本仓库是基于开源项目 [PageIndex](https://github.com/VectifyAI/PageIndex) 进行的下游重构。  
> 我们替换了原有的品牌命名、包结构、CLI 入口和面向产品的说明文档，使这个仓库能够以一个独立项目的形式运行，同时明确保留对上游项目的来源说明。

## 这个项目能做什么

RAG 目前聚焦两个核心工作流：

1. 从长 PDF 或 Markdown 文档中构建结构化树。
2. 在这棵树之上构建本地查询索引，用于确定性检索和可选的 LLM 重排序。

当前实现组合了以下能力：

- 层级化文档解析
- 倒排索引检索
- 可用时使用 Roaring Bitmap postings
- 基于哈希的快速直达查找
- 页码范围过滤
- 对候选结果进行可选的 LLM 重排序

## 关键能力

- 将 PDF 解析为带页码区间和可选摘要的章节树
- 按 Markdown 标题层级构建章节树
- 为本地搜索构建压缩的查询索引工件
- 支持按标题、摘要、路径或叶子节点文本检索
- 支持按叶子节点和页码范围过滤
- 支持用 LLM 对确定性检索结果进行重排序
- 支持本地 benchmark，评估构建、加载和查询延迟

## 项目结构

```text
rag/
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
    storage.py
run_rag.py
tests/
scripts/
docs/
```

## 安装

```bash
python -m pip install -r requirements.txt
```

位图后端依赖 `pyroaring`，该依赖已经包含在 `requirements.txt` 中。

## 环境变量

如果你要使用在线 LLM 重排序，请在本地创建 `.env` 文件：

```bash
MODEL=your_provider_model
API_KEY=your_api_key
API_URL=your_base_url
```

运行时也兼容 OpenAI 风格的环境变量命名，例如 `OPENAI_API_KEY`、`OPENAI_API_BASE` 和 `OPENAI_BASE_URL`。

如果你使用的是 OpenAI-compatible 服务并传入的是服务端原生模型 ID，例如：

```bash
MODEL=Pro/deepseek-ai/DeepSeek-V3.2
```

程序会在底层自动兼容 `litellm` 所需的 provider 前缀，不需要你手动改成 `openai/...`。

## 快速开始

### 构建 PDF 树

```bash
python run_rag.py --pdf_path /path/to/document.pdf
```

### 构建 Markdown 树

```bash
python run_rag.py --md_path /path/to/document.md --if-add-node-summary no
```

### 构建查询索引并执行查询

```bash
python run_rag.py \
  --md_path /path/to/document.md \
  --build-query-index yes \
  --include-text yes \
  --query "direct-to-consumer" \
  --top-k 5
```

### 执行确定性检索并使用 LLM 重排序

```bash
python run_rag.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --query "risk factors liquidity" \
  --top-k 10 \
  --rerank-with-llm yes \
  --rerank-top-k 3
```

### 建一次索引，后续直接查询

第一次先建树并构建索引：

```bash
python run_rag.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --include-text yes
```

后续直接加载已有索引查询，不再重新解析 PDF：

```bash
python run_rag.py \
  --index-path results/document_query_index.pkl.gz \
  --query "retrieval design" \
  --top-k 5
```

### 运行本地索引 benchmark

```bash
python scripts/benchmark_query_index.py \
  --structure-path tests/results/2023-annual-report_structure.json \
  --query "financial stability" \
  --query "supervisory developments"
```

## 对外 Python API

```python
from rag import (
    build_pdf_tree,
    build_markdown_tree,
    build_query_index,
    search_index,
    rerank_query_results,
)
```

主要入口函数：

- `build_pdf_tree(...)`
- `build_markdown_tree(...)`
- `build_query_index(...)`
- `search_index(...)`
- `rerank_query_results(...)`

## 输出内容

默认情况下，CLI 会写出：

- 树结构 JSON：`results/<name>_structure.json`
- 查询索引：`results/<name>_query_index.pkl.gz`

如果你已经有查询索引，也可以通过 `--index-path` 进入 query-only 模式，直接查询而不重新解析源文档。

查询结果会以 JSON 格式输出，并包含：

- `node_id`
- `title`
- `start_index`
- `end_index`
- `score`
- `matched_terms`
- `matched_fields`
- `ancestor_ids`

## 测试

离线测试套件：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_normalizer.py \
  tests/test_postings.py \
  tests/test_index_builder.py \
  tests/test_query_engine.py \
  tests/test_storage.py \
  tests/test_cli.py \
  -q -p no:cacheprovider
```

在线 LLM 冒烟测试：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_llm_rerank_live.py \
  -q -p no:cacheprovider -m live_llm
```

## 来源说明

本项目基于开源的 PageIndex 代码库重构而来，并明确保留与上游项目的关系说明。

- 上游项目：`VectifyAI/PageIndex`
- 当前仓库目标：在保留上游基础能力的前提下，将其重塑为一个拥有独立公共标识、并具备本地混合检索层的结构化 RAG 工具包

请继续遵守上游项目的许可证要求。详见 `LICENSE` 和 `NOTICE.md`。
