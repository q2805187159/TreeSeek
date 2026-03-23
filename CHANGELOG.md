# Changelog

All notable changes to this project will be documented in this file.

## 0.1.0 - 2026-03-23

### Added

- Introduced the `rag` package as the new public project namespace
- Added hybrid query indexing with inverted index plus bitmap and fallback postings
- Added CLI support for index building, querying, and LLM reranking
- Added benchmark and automated test coverage

### Changed

- Replaced the old project-facing branding and entrypoint naming with `RAG` and `run_rag.py`
- Reworked the top-level documentation for the new standalone project identity

### Removed

- Removed the old cookbook and tutorial marketing content from the published project layout
