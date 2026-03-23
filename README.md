# RAG

Structured document retrieval toolkit for turning long PDFs or Markdown files into hierarchical trees and queryable hybrid indexes.

> This repository is a downstream refactor based on the open-source [PageIndex](https://github.com/VectifyAI/PageIndex) project.  
> The original branding, package layout, CLI entrypoints, and product-facing docs were replaced so this repo can stand on its own as a new project while keeping clear attribution to its upstream foundation.

## What This Project Does

RAG focuses on two practical workflows:

1. Build a structured tree from a long PDF or Markdown document.
2. Build a local query index on top of that tree for deterministic retrieval and optional LLM reranking.

The current implementation combines:

- Hierarchical document parsing
- Inverted index retrieval
- Roaring Bitmap postings when available
- Hash-based direct lookup
- Page-range filtering
- Optional LLM reranking over a reduced candidate set

## Key Capabilities

- Parse PDFs into section trees with page spans and optional summaries
- Parse Markdown into section trees based on heading levels
- Build a compressed query index artifact for local search
- Search by title, summary, path, or leaf text
- Filter by leaf nodes and page ranges
- Rerank deterministic search results with an LLM
- Benchmark build, load, and query latency locally

## Project Layout

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

## Installation

```bash
python -m pip install -r requirements.txt
```

The bitmap backend uses `pyroaring`. It is already listed in `requirements.txt`.

## Environment Variables

Create a local `.env` file if you want to use live LLM reranking:

```bash
MODEL=your_provider_model
API_KEY=your_api_key
API_URL=your_base_url
```

The runtime also supports OpenAI-compatible names such as `OPENAI_API_KEY`, `OPENAI_API_BASE`, and `OPENAI_BASE_URL`.

## Quick Start

### Build a PDF tree

```bash
python run_rag.py --pdf_path /path/to/document.pdf
```

### Build a Markdown tree

```bash
python run_rag.py --md_path /path/to/document.md --if-add-node-summary no
```

### Build a query index and run a query

```bash
python run_rag.py \
  --md_path /path/to/document.md \
  --build-query-index yes \
  --include-text yes \
  --query "direct-to-consumer" \
  --top-k 5
```

### Run deterministic search with LLM rerank

```bash
python run_rag.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --query "risk factors liquidity" \
  --top-k 10 \
  --rerank-with-llm yes \
  --rerank-top-k 3
```

### Benchmark the local index

```bash
python scripts/benchmark_query_index.py \
  --structure-path tests/results/2023-annual-report_structure.json \
  --query "financial stability" \
  --query "supervisory developments"
```

## Public Python API

```python
from rag import (
    build_pdf_tree,
    build_markdown_tree,
    build_query_index,
    search_index,
    rerank_query_results,
)
```

Main entrypoints:

- `build_pdf_tree(...)`
- `build_markdown_tree(...)`
- `build_query_index(...)`
- `search_index(...)`
- `rerank_query_results(...)`

## Outputs

By default, the CLI writes:

- Tree JSON: `results/<name>_structure.json`
- Query index: `results/<name>_query_index.pkl.gz`

The query response is printed as JSON and includes:

- `node_id`
- `title`
- `start_index`
- `end_index`
- `score`
- `matched_terms`
- `matched_fields`
- `ancestor_ids`

## Testing

Offline test suite:

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

Live LLM smoke test:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_llm_rerank_live.py \
  -q -p no:cacheprovider -m live_llm
```

## Attribution

This project is based on the open-source PageIndex codebase and keeps that upstream relationship explicit.

- Upstream project: `VectifyAI/PageIndex`
- Current repository goal: reshape that foundation into a standalone structured RAG toolkit with a different public identity and a refactored local retrieval layer

The upstream license should continue to be respected. See `LICENSE` and `NOTICE.md`.
