from __future__ import annotations

from .filters import apply_filters
from .models import QueryIndexArtifact, QueryRequest, QueryResult
from .normalizer import extract_phrases, normalize_text, tokenize
from .postings import create_posting_list
from .scoring import score_candidate
from .snippets import build_result_snippet


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


def _dedupe_key(index: QueryIndexArtifact, node_idx: int):
    normalized_fields = index.normalized_fields.get(node_idx, {})
    node = index.nodes[node_idx]
    summary_key = normalized_fields.get("summary")
    if summary_key:
        return ("summary", summary_key)
    return ("node", normalized_fields.get("title", ""), node.start_index, node.end_index)


def _page_overlap_ratio(left_start: int, left_end: int, right_start: int, right_end: int) -> float:
    left_span = max(left_end - left_start + 1, 1)
    right_span = max(right_end - right_start + 1, 1)
    overlap = max(0, min(left_end, right_end) - max(left_start, right_start) + 1)
    if overlap <= 0:
        return 0.0
    return overlap / min(left_span, right_span)


def _apply_diversity_selection(index: QueryIndexArtifact, scored_candidates: list[dict], top_k: int, debug_explain: bool):
    selected: list[dict] = []
    remaining = list(scored_candidates)
    diversity_penalty = float(getattr(index, "diversity_penalty", 0.75))

    while remaining and len(selected) < top_k:
        best_candidate = None
        best_effective_score = None

        for candidate in remaining:
            node = index.nodes[candidate["node_idx"]]
            effective_score = candidate["raw_score"]
            penalties = []

            for chosen in selected:
                chosen_node = index.nodes[chosen["node_idx"]]
                same_parent = node.parent_id is not None and node.parent_id == chosen_node.parent_id
                overlap_ratio = _page_overlap_ratio(node.start_index, node.end_index, chosen_node.start_index, chosen_node.end_index)
                if same_parent or overlap_ratio > 0.7:
                    effective_score -= diversity_penalty
                    penalties.append(
                        {
                            "name": "diversity_penalty",
                            "value": round(-diversity_penalty, 6),
                            "field": "post_ranking",
                            "reason": "same_parent" if same_parent else "page_overlap",
                        }
                    )

            if best_effective_score is None or effective_score > best_effective_score:
                best_candidate = candidate.copy()
                best_candidate["effective_score"] = effective_score
                if debug_explain and penalties:
                    best_candidate.setdefault("bonuses_applied", [])
                    best_candidate["bonuses_applied"] = list(best_candidate["bonuses_applied"]) + penalties
                best_effective_score = effective_score

        selected.append(best_candidate)
        remaining = [candidate for candidate in remaining if candidate["node_idx"] != best_candidate["node_idx"]]

    return selected


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
    debug_explain: bool | None = None,
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
            debug_explain=debug_explain if debug_explain is not None else False,
        )

    if debug_explain is None:
        request.debug_explain = bool(
            request.debug_explain if isinstance(query, QueryRequest) else getattr(index, "debug_explain_default", False)
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

    scored_candidates: list[dict] = []
    for node_idx in candidate_indices:
        score_data = score_candidate(
            index,
            node_idx,
            query_terms=query_terms,
            phrases=phrases,
            normalized_query=normalized_query,
            query_node_id=query_node_id,
            debug_explain=request.debug_explain,
        )
        if score_data["raw_score"] <= 0:
            continue
        scored_candidates.append(
            {
                "node_idx": node_idx,
                "dedupe_key": _dedupe_key(index, node_idx),
                **score_data,
            }
        )

    deduped_candidates: dict[tuple, dict] = {}
    for candidate in scored_candidates:
        existing = deduped_candidates.get(candidate["dedupe_key"])
        if existing is None or candidate["raw_score"] > existing["raw_score"]:
            deduped_candidates[candidate["dedupe_key"]] = candidate

    ranked_candidates = sorted(
        deduped_candidates.values(),
        key=lambda item: (-item["raw_score"], index.nodes[item["node_idx"]].start_index, index.nodes[item["node_idx"]].node_id),
    )
    selected_candidates = _apply_diversity_selection(index, ranked_candidates, request.top_k, request.debug_explain)

    scored_results: list[QueryResult] = []
    for candidate in selected_candidates:
        node_idx = candidate["node_idx"]
        node = index.nodes[node_idx]
        snippet, highlight_terms, snippet_field = build_result_snippet(
            node,
            query_terms=query_terms,
            max_chars=getattr(index, "snippet_max_chars", 320),
            context_chars=getattr(index, "snippet_context_chars", 120),
        )
        scored_results.append(
            QueryResult(
                doc_id=node.doc_id,
                node_id=node.node_id,
                title=node.title,
                start_index=node.start_index,
                end_index=node.end_index,
                score=round(candidate["raw_score"], 6),
                matched_terms=candidate["matched_terms"],
                matched_fields=candidate["matched_fields"],
                ancestor_ids=_ancestor_ids(index, node.node_id, request.expand_ancestors),
                summary=node.summary or node.prefix_summary,
                snippet=snippet,
                highlight_terms=highlight_terms,
                snippet_field=snippet_field,
                field_scores=candidate["field_scores"] if request.debug_explain else None,
                bonuses_applied=candidate["bonuses_applied"] if request.debug_explain else [],
                phrase_matches=candidate["phrase_matches"] if request.debug_explain else None,
            )
        )

    return scored_results
