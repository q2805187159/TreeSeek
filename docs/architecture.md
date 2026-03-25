# TreeSeek Architecture

## Overview

TreeSeek is a structured long-document retrieval toolkit built from a downstream refactor of PageIndex.

It keeps the useful upstream ideas:

- hierarchical document trees
- section-level summaries
- document-aware retrieval

It extends them with a more engineering-oriented local retrieval layer:

- local query index artifacts
- BM25-lite scoring
- snippet/highlight extraction
- query-only CLI mode
- controlled LLM concurrency and request throttling

## Core Flow

```text
PDF / Markdown
  -> tree builder
  -> structured nodes
  -> query index builder
  -> deterministic retrieval
  -> optional LLM rerank
```

## Main Components

- `treeseek/pdf_tree.py`
  - PDF structure extraction, TOC handling, recursive subtree splitting
- `treeseek/markdown_tree.py`
  - Markdown heading-based tree generation
- `treeseek/indexing/builder.py`
  - local index artifact construction
- `treeseek/indexing/query_engine.py`
  - candidate generation, scoring, dedupe, diversity, explain
- `treeseek/indexing/llm_rerank.py`
  - optional reranking over top candidates
- `treeseek/utils.py`
  - provider compatibility, retry/backoff, concurrency and RPM control

## Attribution

TreeSeek is not presented as the original PageIndex repository.
It is a separately branded downstream project built on that upstream foundation.
