from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from treeseek import (
    build_pdf_tree_from_opt,
    build_query_index,
    build_word_tree,
    load_query_index,
    rerank_query_results,
    save_query_index,
    search_index,
)
from treeseek.markdown_tree import build_markdown_tree
from treeseek.corpus.corpus_builder import _build_pdf_tree_fallback
from treeseek.utils import ConfigLoader


def build_single_index(path: str, doc_type: str, *, include_text: bool, index_output_dir: str):
    opt = ConfigLoader().load({"index_include_text": "yes" if include_text else "no", "if_add_node_summary": "no", "if_add_doc_description": "no", "if_add_node_text": "yes" if include_text else "no"})

    if doc_type == "pdf":
        try:
            result = build_pdf_tree_from_opt(path, opt)
        except Exception:
            result = _build_pdf_tree_fallback(Path(path))
    elif doc_type == "markdown":
        result = asyncio.run(
            build_markdown_tree(
                md_path=path,
                if_thinning=False,
                min_token_threshold=5000,
                if_add_node_summary=opt.if_add_node_summary,
                summary_token_threshold=200,
                model=opt.model,
                if_add_doc_description=opt.if_add_doc_description,
                if_add_node_text=opt.if_add_node_text,
                if_add_node_id=opt.if_add_node_id,
            )
        )
    elif doc_type == "word":
        result = asyncio.run(
            build_word_tree(
                docx_path=path,
                if_thinning=False,
                min_token_threshold=5000,
                if_add_node_summary=opt.if_add_node_summary,
                summary_token_threshold=200,
                model=opt.model,
                if_add_doc_description=opt.if_add_doc_description,
                if_add_node_text=opt.if_add_node_text,
                if_add_node_id=opt.if_add_node_id,
            )
        )
    else:
        raise ValueError(f"Unsupported doc_type: {doc_type}")

    os.makedirs(index_output_dir, exist_ok=True)
    doc_name = result["doc_name"]
    stem = os.path.splitext(os.path.basename(doc_name))[0]
    structure_path = os.path.join(index_output_dir, f"{stem}_structure.json")
    index_path = os.path.join(index_output_dir, f"{stem}_query_index.pkl.gz")

    with open(structure_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    query_index = build_query_index(
        result,
        include_text=include_text,
        postings_backend=opt.index_postings_backend,
        field_weights={
            "title": opt.weight_title,
            "path_titles": opt.weight_path,
            "summary": opt.weight_summary,
            "prefix_summary": opt.weight_prefix_summary,
            "text": opt.weight_text,
        },
        bonuses={
            "exact_title": opt.bonus_exact_title,
            "phrase": opt.bonus_phrase,
            "leaf": opt.bonus_leaf,
            "all_terms_hit": opt.bonus_all_terms_hit,
            "proximity": opt.bonus_proximity,
        },
        snippet_max_chars=opt.snippet_max_chars,
        snippet_context_chars=opt.snippet_context_chars,
        debug_explain_default=False,
        bm25_k1=opt.bm25_k1,
        bm25_b=opt.bm25_b,
        proximity_window=opt.proximity_window,
        diversity_penalty=opt.diversity_penalty,
    )
    save_query_index(query_index, index_path)
    return {
        "doc_name": doc_name,
        "structure_path": structure_path,
        "index_path": index_path,
    }


def query_single_index(index_path: str, query: str, *, top_k: int, leaf_only: bool, debug_explain: bool, rerank_with_llm: bool):
    index = load_query_index(index_path)
    results = search_index(index, query, top_k=top_k, leaf_only=leaf_only, debug_explain=debug_explain)
    if rerank_with_llm:
        results = rerank_query_results(index, query, results)
    return {
        "doc_name": index.doc_id,
        "query": query,
        "index_path": index_path,
        "results": [item.to_dict() for item in results],
    }


def rerank_existing_results(index_path: str, query: str, *, top_k: int):
    index = load_query_index(index_path)
    results = search_index(index, query, top_k=top_k)
    reranked = rerank_query_results(index, query, results, top_k=top_k)
    return {
        "doc_name": index.doc_id,
        "query": query,
        "index_path": index_path,
        "results": [item.to_dict() for item in reranked],
    }
