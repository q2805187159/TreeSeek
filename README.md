# TreeSeek

Structured, local-first retrieval toolkit for long PDFs and Markdown documents.

> TreeSeek is a downstream refactor based on the open-source [PageIndex](https://github.com/VectifyAI/PageIndex) project.  
> It keeps the useful upstream idea of hierarchical document trees, while rebuilding the engineering surface around local indexing, controllable querying, explainability, and production-oriented runtime controls.

---

## What Is TreeSeek

TreeSeek is designed for teams that need to work with long professional documents where:

- structure matters more than chunk similarity
- page ranges and section boundaries matter
- answers need to be traceable
- local indexing and repeated querying should be cheap and controllable

TreeSeek currently focuses on two major workflows:

1. Build a structured tree from PDF or Markdown documents
2. Build a local query index on top of that tree for continuous retrieval

Current retrieval stack includes:

- hierarchical document parsing
- local inverted index
- Roaring Bitmap postings when available
- BM25-lite ranking
- phrase and proximity bonuses
- snippet and highlight extraction
- optional LLM reranking
- query-only mode with prebuilt index reuse

## TreeSeek vs Original PageIndex

| Item | Original PageIndex | TreeSeek |
| --- | --- | --- |
| Public identity | Product-style PageIndex branding | Independent TreeSeek branding |
| Main package | `pageindex` | `treeseek` |
| CLI entry | `run_pageindex.py` | `run_treeseek.py` |
| Focus | Tree generation and reasoning-oriented retrieval narrative | Tree generation plus local hybrid retrieval, explainability, and runtime controls |
| Query reuse | More external-workflow oriented | Built-in `--index-path` query-only mode |
| Ranking | Tree + LLM reasoning emphasis | BM25-lite + phrase + proximity + diversity + optional rerank |
| Runtime controls | Not the main emphasis in README | Explicit concurrency, RPM, retry, and debug controls |

## Core Capabilities

- Parse PDFs into hierarchical section trees
- Parse Markdown headings into trees
- Build local query indexes for repeated retrieval
- Return `snippet`, `highlight_terms`, and `snippet_field`
- Support explain mode with `field_scores`, `bonuses_applied`, and `phrase_matches`
- Reuse prebuilt indexes without reparsing source files
- Run with OpenAI-compatible providers via LiteLLM
- Apply built-in concurrency and RPM controls for fragile provider limits

## Suitable Scenarios

| Scenario | Typical Documents | Why TreeSeek Fits |
| --- | --- | --- |
| Finance and investment research | annual reports, quarterly filings, earnings decks, prospectuses | strong structure, long sections, page-sensitive evidence |
| Legal and compliance | contracts, regulations, audit manuals, internal policies | traceable section retrieval is more important than loose similarity |
| Technical documentation | API docs, deployment manuals, architecture docs, runbooks | heading hierarchy is strong and repeated querying is common |
| Enterprise knowledge base | SOPs, training docs, FAQs, internal standards | local indexing and repeatable query flows reduce support cost |
| Manufacturing and operations | equipment manuals, maintenance guides, incident playbooks | page ranges, tables, and procedural sections matter |
| Public sector and policy | notices, standards, policy documents, reports | long-form structured documents benefit from explainable retrieval |

## Commercial Value

| Value Direction | Practical Impact |
| --- | --- |
| Lower document handling cost | replace manual PDF searching with structured local retrieval |
| Better traceability | every result stays tied to title, page span, and snippet |
| Easier private deployment | no external vector DB is required for the core workflow |
| Better repeated-query economics | build once, query many times with `--index-path` |
| Better debugging and tuning | explain mode and runtime controls make retrieval behavior inspectable |

## Project Layout

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

## Installation

```bash
python -m pip install -r requirements.txt
```

Notes:

- `pyroaring` is included for bitmap posting acceleration
- LiteLLM is used as the unified model adapter layer
- TreeSeek is tuned for OpenAI-compatible providers by default

## Configuration Template

Use [`.env.example`](/e:/python/PageIndex/.env.example) as the starting template.

Recommended flow:

1. Copy `.env.example` to `.env`
2. Fill in `MODEL`, `API_KEY`, and `API_URL`
3. Adjust TreeSeek runtime limits only if your provider requires it

## Quick Start

### Build a PDF tree

```bash
python run_treeseek.py --pdf_path /path/to/document.pdf
```

### Build a Markdown tree

```bash
python run_treeseek.py --md_path /path/to/document.md --if-add-node-summary no
```

### Build an index and query immediately

```bash
python run_treeseek.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --include-text yes \
  --query "retrieval design" \
  --top-k 5
```

### Build once, query many times

First build the index:

```bash
python run_treeseek.py \
  --pdf_path /path/to/document.pdf \
  --build-query-index yes \
  --include-text yes
```

Then reuse it directly:

```bash
python run_treeseek.py \
  --index-path results/document_query_index.pkl.gz \
  --query "retrieval design" \
  --top-k 5
```

### Show explain fields

```bash
python run_treeseek.py \
  --index-path results/document_query_index.pkl.gz \
  --query "\"retrieval design\"" \
  --top-k 5 \
  --debug-explain yes
```

### Run the benchmark

```bash
python scripts/benchmark_query_index.py \
  --structure-path tests/results/2023-annual-report_structure.json \
  --query "financial stability" \
  --query "supervisory developments"
```

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

Main entrypoints:

- `build_pdf_tree(...)`
- `build_markdown_tree(...)`
- `build_query_index(...)`
- `search_index(...)`
- `rerank_query_results(...)`

## Query Output

Default query results include:

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

When `--debug-explain yes` is enabled, TreeSeek also returns:

- `field_scores`
- `bonuses_applied`
- `phrase_matches`

## Runtime Controls

TreeSeek exposes several runtime safety controls via environment variables:

- `TREESEEK_LLM_MAX_CONCURRENCY`
- `TREESEEK_LLM_MAX_RPM`
- `TREESEEK_LLM_RETRY_BASE_DELAY`
- `TREESEEK_LLM_RETRY_MAX_DELAY`
- `TREESEEK_DEBUG_LOGS`

These are especially useful when your model provider has strict organization-level concurrency or RPM limits.

## Testing

Recommended offline regression run:

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

Optional live LLM smoke test:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/test_llm_rerank_live.py \
  -q -p no:cacheprovider -m live_llm
```

## Documentation

- [Architecture](docs/architecture.md)
- [Enhancement Roadmap](docs/treeseek_enhancement_roadmap.md)

## Attribution

TreeSeek is a downstream refactor built from the PageIndex codebase.

- Upstream project: `VectifyAI/PageIndex`
- Current goal: transform the upstream tree-oriented idea into a cleaner, local-first, engineering-oriented long-document retrieval toolkit

Please continue to respect the upstream license terms.
See:

- `LICENSE`
- `NOTICE.md`
