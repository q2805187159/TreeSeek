from __future__ import annotations

from importlib import import_module

__all__ = [
    "build_pdf_tree",
    "build_pdf_tree_from_opt",
    "build_markdown_tree",
    "build_query_index",
    "flatten_tree",
    "load_query_index",
    "rerank_query_results",
    "save_query_index",
    "search_index",
]

_MODULE_BY_EXPORT = {
    "build_pdf_tree": "rag.pdf_tree",
    "build_pdf_tree_from_opt": "rag.pdf_tree",
    "build_markdown_tree": "rag.markdown_tree",
    "build_query_index": "rag.indexing.builder",
    "flatten_tree": "rag.indexing.builder",
    "load_query_index": "rag.indexing.storage",
    "save_query_index": "rag.indexing.storage",
    "search_index": "rag.indexing.query_engine",
    "rerank_query_results": "rag.indexing.llm_rerank",
}


def __getattr__(name: str):
    module_name = _MODULE_BY_EXPORT.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
