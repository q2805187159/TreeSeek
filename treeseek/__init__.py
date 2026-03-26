from __future__ import annotations

from importlib import import_module

__all__ = [
    "build_pdf_tree",
    "build_pdf_tree_from_opt",
    "build_markdown_tree",
    "build_word_tree",
    "build_query_index",
    "flatten_tree",
    "load_query_index",
    "rerank_query_results",
    "save_query_index",
    "search_index",
    "build_corpus_from_directory",
    "load_corpus_index",
    "save_corpus_index",
    "search_corpus",
]

_MODULE_BY_EXPORT = {
    "build_pdf_tree": "treeseek.pdf_tree",
    "build_pdf_tree_from_opt": "treeseek.pdf_tree",
    "build_markdown_tree": "treeseek.markdown_tree",
    "build_word_tree": "treeseek.word_tree",
    "build_query_index": "treeseek.indexing.builder",
    "flatten_tree": "treeseek.indexing.builder",
    "load_query_index": "treeseek.indexing.storage",
    "save_query_index": "treeseek.indexing.storage",
    "search_index": "treeseek.indexing.query_engine",
    "rerank_query_results": "treeseek.indexing.llm_rerank",
    "build_corpus_from_directory": "treeseek.corpus.corpus_builder",
    "load_corpus_index": "treeseek.corpus.corpus_storage",
    "save_corpus_index": "treeseek.corpus.corpus_storage",
    "search_corpus": "treeseek.corpus.corpus_query",
}


def __getattr__(name: str):
    module_name = _MODULE_BY_EXPORT.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
