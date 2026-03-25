# Changelog

All notable changes to TreeSeek will be documented in this file.

## 0.2.0 - 2026-03-25

### Added

- Renamed the public project identity to `TreeSeek`
- Added `.env.example` with documented runtime configuration
- Added BM25-lite, phrase matching, proximity bonus, snippet/highlight, and explain mode
- Added safer concurrency and RPM throttling for LLM calls

### Changed

- Renamed the public package namespace from `rag` to `treeseek`
- Renamed the CLI entrypoint to `run_treeseek.py`
- Removed default file log generation to keep the project clean
- Cleaned debug-specific assets and reduced nonessential tests

### Removed

- Removed temporary debug-only PDF artifacts and internal implementation-debug tests
