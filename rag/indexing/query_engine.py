from __future__ import annotations

from .filters import apply_filters
from .models import QueryIndexArtifact, QueryRequest, QueryResult
from .normalizer import extract_phrases, normalize_text, tokenize
from .postings import create_posting_list
from .scoring import score_candidate


def _ancestor_ids(index: QueryIndexArtifact, node_id: str, limit: int) -> list[str]:
    if limit <= 0:
        return []
    chain: list[str] = []
    current = index.parent_map.get(node_id)
    while current and len(chain) < limit:
        chain.append(current)
        current = index.parent_map.get(current)
    return list(reversed(chain))


def _collect_candidates(index: QueryIndexArtifact, query_terms: list[str], normalized_query: str, query_node_id: str | None):
    combined = create_posting_list(backend=index.postings_backend)
    term_mappings = [
        index.title_terms,
        index.summary_terms,
        index.prefix_summary_terms,
        index.path_terms,
        index.text_terms,
    ]

    for term in query_terms:
        for mapping in term_mappings:
            posting = mapping.get(term)
            if posting is not None:
                combined = combined.union(posting)

    for title_id in index.normalized_title_to_ids.get(normalized_query, []):
        combined.add(index.node_id_to_idx[title_id])

    if query_node_id:
        combined.add(index.node_id_to_idx[query_node_id])

    return combined


def search_index(
    index: QueryIndexArtifact,
    query: str | QueryRequest,
    *,
    top_k: int | None = None,
    expand_ancestors: int | None = None,
    leaf_only: bool | None = None,
    depth: int | None = None,
    min_page: int | None = None,
    max_page: int | None = None,
) -> list[QueryResult]:
    if isinstance(query, QueryRequest):
        request = query
    else:
        request = QueryRequest(
            query=query,
            top_k=top_k or 10,
            expand_ancestors=expand_ancestors if expand_ancestors is not None else 1,
            leaf_only=leaf_only if leaf_only is not None else False,
            depth=depth,
            min_page=min_page,
            max_page=max_page,
        )

    normalized_query = normalize_text(request.query)
    query_terms = list(dict.fromkeys(tokenize(request.query)))
    phrases = extract_phrases(request.query)
    query_node_id = request.query.strip() if request.query.strip() in index.node_id_to_idx else None

    candidates = _collect_candidates(index, query_terms, normalized_query, query_node_id)
    if len(candidates) == 0:
        return []

    filtered = apply_filters(
        index,
        candidates,
        leaf_only=request.leaf_only,
        depth=request.depth,
        min_page=request.min_page,
        max_page=request.max_page,
    )
    candidate_indices = filtered.to_list()
    if not candidate_indices:
        return []

    scored_results: list[QueryResult] = []
    for node_idx in candidate_indices:
        score, matched_terms, matched_fields = score_candidate(
            index,
            node_idx,
            query_terms=query_terms,
            phrases=phrases,
            normalized_query=normalized_query,
            query_node_id=query_node_id,
        )
        if score <= 0:
            continue
        node = index.nodes[node_idx]
        scored_results.append(
            QueryResult(
                doc_id=node.doc_id,
                node_id=node.node_id,
                title=node.title,
                start_index=node.start_index,
                end_index=node.end_index,
                score=round(score, 6),
                matched_terms=matched_terms,
                matched_fields=matched_fields,
                ancestor_ids=_ancestor_ids(index, node.node_id, request.expand_ancestors),
                summary=node.summary or node.prefix_summary,
            )
        )

    scored_results.sort(key=lambda item: (-item.score, item.start_index, item.node_id))
    return scored_results[: request.top_k]
