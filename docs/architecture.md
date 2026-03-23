# RAG Architecture

## Overview

RAG is a structured document retrieval toolkit built on top of a downstream refactor of PageIndex.

The current architecture keeps the useful upstream ideas:

- hierarchical document trees
- section-level summaries
- document-aware retrieval

It replaces the original project-facing packaging and retrieval surface with a new standalone layout centered on a local hybrid index.

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

- `rag/pdf_tree.py`
  - builds tree structures from PDF inputs
- `rag/markdown_tree.py`
  - builds tree structures from Markdown inputs
- `rag/indexing/builder.py`
  - flattens trees and constructs the local query artifact
- `rag/indexing/query_engine.py`
  - performs deterministic search, filtering, scoring, and ancestor expansion
- `rag/indexing/llm_rerank.py`
  - reranks the top deterministic candidates with an LLM

## Retrieval Model

The local search layer uses:

- inverted index postings for term lookup
- Roaring Bitmap postings when available
- hash lookups for node IDs and normalized titles
- page-range filtering
- weighted scoring across title, summary, path, prefix summary, and optional leaf text

## Attribution

This repository is not presented as the original PageIndex project.
It is an independently branded downstream refactor built from that upstream foundation, and the README keeps that lineage explicit.
