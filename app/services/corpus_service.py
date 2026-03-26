from __future__ import annotations

from treeseek import build_corpus_from_directory, load_corpus_index, search_corpus
from treeseek.corpus.corpus_models import CorpusQueryRequest


def build_corpus(input_dir: str, corpus_name: str, exclude_globs: list[str] | None = None):
    corpus_index, corpus_index_path = build_corpus_from_directory(
        input_dir,
        corpus_name=corpus_name,
        output_dir="./results/corpus",
        user_opt={
            "if_add_node_summary": "no",
            "if_add_doc_description": "no",
            "if_add_node_text": "yes",
            "index_include_text": "yes",
        },
        exclude_globs=exclude_globs or [],
    )
    return {
        "corpus_name": corpus_index.corpus_name,
        "corpus_index_path": corpus_index_path,
        "document_count": len(corpus_index.documents),
    }


def query_corpus(
    corpus_index_path: str,
    query: str,
    *,
    top_k: int,
    doc_id: str | None,
    doc_type: str | None,
    tags: list[str],
    source: str | None,
    created_at_from: str | None,
    created_at_to: str | None,
    leaf_only: bool,
    debug_explain: bool,
    rerank_with_llm: bool,
):
    corpus_index = load_corpus_index(corpus_index_path)
    request = CorpusQueryRequest(
        query=query,
        top_k=top_k,
        doc_id=doc_id,
        doc_type=doc_type,
        tags=tags,
        source=source,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        leaf_only=leaf_only,
        debug_explain=debug_explain,
        rerank_with_llm=rerank_with_llm,
    )
    results = search_corpus(corpus_index, request)
    return {
        "corpus_name": corpus_index.corpus_name,
        "query": query,
        "corpus_index_path": corpus_index_path,
        "results": [item.to_dict() for item in results],
    }
