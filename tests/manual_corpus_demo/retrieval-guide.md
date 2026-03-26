# Retrieval Guide

## Retrieval Design

This guide explains retrieval design for long documents.
It emphasizes deterministic candidate generation, BM25-lite ranking, snippet extraction, and explain mode.

## Observability

Observability is important for debugging.
Useful signals include matched fields, matched terms, candidate counts, and final ranking order.

## Corpus Workflow

Build the corpus once, then reuse `corpus_index.pkl.gz` for repeated queries.
Use metadata filters such as `doc_type`, `source`, and `doc_id` to narrow results.
