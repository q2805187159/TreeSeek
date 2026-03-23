from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from .models import IndexedNode, QueryIndexArtifact
from .normalizer import count_terms, normalize_text, normalize_title_key, tokenize
from .postings import create_posting_list, resolve_postings_backend

DEFAULT_FIELD_WEIGHTS = {
    "title": 5.0,
    "path_titles": 3.5,
    "summary": 3.0,
    "prefix_summary": 2.5,
    "text": 1.0,
}

DEFAULT_BONUSES = {
    "exact_title": 5.0,
    "phrase": 3.0,
    "leaf": 1.0,
    "all_terms_hit": 2.0,
}


def _resolve_roots_and_doc_id(document, doc_id: str | None = None):
    if isinstance(document, dict):
        roots = document.get("structure", document)
        resolved_doc_id = doc_id or document.get("doc_name") or "document"
    else:
        roots = document
        resolved_doc_id = doc_id or "document"
    if not isinstance(roots, list):
        raise TypeError("document structure must be a list of root nodes or a dict containing 'structure'")
    return roots, resolved_doc_id


def flatten_tree(document, doc_id: str | None = None) -> list[IndexedNode]:
    roots, resolved_doc_id = _resolve_roots_and_doc_id(document, doc_id)
    nodes: list[IndexedNode] = []
    counter = 0

    def walk(node_dict: dict, parent_id: str | None, ancestor_titles: list[str], depth: int) -> IndexedNode:
        nonlocal counter
        current_id = str(node_dict.get("node_id") or f"auto-{counter:04d}")
        counter += 1
        children = node_dict.get("nodes") or []
        title = str(node_dict.get("title") or "").strip()
        path_titles = [*ancestor_titles, title] if title else list(ancestor_titles)
        start_index = node_dict.get("start_index", node_dict.get("line_num", 0)) or 0
        end_index = node_dict.get("end_index", node_dict.get("line_num", start_index)) or start_index
        text = node_dict.get("text")
        summary = node_dict.get("summary")
        prefix_summary = node_dict.get("prefix_summary")
        indexed_node = IndexedNode(
            doc_id=resolved_doc_id,
            node_id=current_id,
            title=title,
            summary=summary,
            prefix_summary=prefix_summary,
            text=text,
            start_index=int(start_index),
            end_index=int(end_index),
            depth=depth,
            parent_id=parent_id,
            path_titles=path_titles,
            token_count=len(tokenize(text or summary or prefix_summary or title)),
        )
        nodes.append(indexed_node)
        child_ids = []
        for child in children:
            child_node = walk(child, current_id, path_titles, depth + 1)
            child_ids.append(child_node.node_id)
        indexed_node.child_ids = child_ids
        indexed_node.is_leaf = not child_ids
        return indexed_node

    for root in roots:
        walk(root, None, [], 1)
    return nodes


def _ensure_posting(mapping: dict, key, backend: str):
    posting = mapping.get(key)
    if posting is None:
        posting = create_posting_list(backend=backend)
        mapping[key] = posting
    return posting


def _add_terms(mapping: dict, term_counts, node_idx: int, backend: str):
    for term in term_counts:
        _ensure_posting(mapping, term, backend).add(node_idx)


def build_query_index(
    document,
    doc_id: str | None = None,
    *,
    include_text: bool = False,
    postings_backend: str = "bitmap",
    field_weights: dict[str, float] | None = None,
    bonuses: dict[str, float] | None = None,
) -> QueryIndexArtifact:
    roots, resolved_doc_id = _resolve_roots_and_doc_id(document, doc_id)
    nodes = flatten_tree({"doc_name": resolved_doc_id, "structure": deepcopy(roots)}, resolved_doc_id)
    backend = resolve_postings_backend(postings_backend)

    node_id_to_idx = {node.node_id: idx for idx, node in enumerate(nodes)}
    normalized_title_to_ids = defaultdict(list)
    parent_map = {node.node_id: node.parent_id for node in nodes}
    children_map = {node.node_id: list(node.child_ids) for node in nodes}
    title_terms = {}
    summary_terms = {}
    prefix_summary_terms = {}
    path_terms = {}
    text_terms = {}
    depth_filter = {}
    leaf_filter = {}
    page_filter = {}
    field_term_frequencies: dict[int, dict[str, dict[str, int]]] = {}
    normalized_fields: dict[int, dict[str, str]] = {}

    for idx, node in enumerate(nodes):
        normalized_title_to_ids[normalize_title_key(node.title)].append(node.node_id)
        _ensure_posting(depth_filter, node.depth, backend).add(idx)
        _ensure_posting(leaf_filter, node.is_leaf, backend).add(idx)
        for page in range(node.start_index, node.end_index + 1):
            _ensure_posting(page_filter, page, backend).add(idx)

        normalized_fields[idx] = {
            "title": normalize_text(node.title),
            "summary": normalize_text(node.summary),
            "prefix_summary": normalize_text(node.prefix_summary),
            "path_titles": normalize_text(" ".join(node.path_titles)),
            "text": normalize_text(node.text if include_text and node.is_leaf else ""),
        }
        field_term_frequencies[idx] = {}

        title_counts = count_terms(node.title)
        field_term_frequencies[idx]["title"] = dict(title_counts)
        _add_terms(title_terms, title_counts, idx, backend)

        path_counts = count_terms(" ".join(node.path_titles))
        field_term_frequencies[idx]["path_titles"] = dict(path_counts)
        _add_terms(path_terms, path_counts, idx, backend)

        summary_counts = count_terms(node.summary)
        field_term_frequencies[idx]["summary"] = dict(summary_counts)
        _add_terms(summary_terms, summary_counts, idx, backend)

        prefix_summary_counts = count_terms(node.prefix_summary)
        field_term_frequencies[idx]["prefix_summary"] = dict(prefix_summary_counts)
        _add_terms(prefix_summary_terms, prefix_summary_counts, idx, backend)

        if include_text and node.is_leaf and node.text:
            text_counts = count_terms(node.text)
            field_term_frequencies[idx]["text"] = dict(text_counts)
            _add_terms(text_terms, text_counts, idx, backend)
        else:
            field_term_frequencies[idx]["text"] = {}

    return QueryIndexArtifact(
        doc_id=resolved_doc_id,
        nodes=nodes,
        node_id_to_idx=node_id_to_idx,
        normalized_title_to_ids=dict(normalized_title_to_ids),
        parent_map=parent_map,
        children_map=children_map,
        title_terms=title_terms,
        summary_terms=summary_terms,
        prefix_summary_terms=prefix_summary_terms,
        path_terms=path_terms,
        text_terms=text_terms,
        depth_filter=depth_filter,
        leaf_filter=leaf_filter,
        page_filter=page_filter,
        field_term_frequencies=field_term_frequencies,
        normalized_fields=normalized_fields,
        field_weights={**DEFAULT_FIELD_WEIGHTS, **(field_weights or {})},
        bonuses={**DEFAULT_BONUSES, **(bonuses or {})},
        postings_backend=backend,
        include_text=include_text,
    )
