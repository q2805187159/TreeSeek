from __future__ import annotations

from .models import QueryIndexArtifact


def score_candidate(
    index: QueryIndexArtifact,
    node_idx: int,
    query_terms: list[str],
    phrases: list[str],
    normalized_query: str,
    query_node_id: str | None = None,
):
    node = index.nodes[node_idx]
    field_terms = index.field_term_frequencies.get(node_idx, {})
    normalized_fields = index.normalized_fields.get(node_idx, {})

    score = 0.0
    matched_terms: set[str] = set()
    matched_fields: set[str] = set()

    for field_name, term_counts in field_terms.items():
        field_weight = float(index.field_weights.get(field_name, 0.0))
        if field_weight <= 0:
            continue
        for term in query_terms:
            count = int(term_counts.get(term, 0))
            if count:
                score += field_weight * count
                matched_terms.add(term)
                matched_fields.add(field_name)

    if normalized_query and normalized_fields.get("title") == normalized_query:
        score += float(index.bonuses.get("exact_title", 0.0))
        matched_fields.add("title")

    if query_node_id and node.node_id == query_node_id:
        score += float(index.bonuses.get("exact_title", 0.0))
        matched_fields.add("title")

    for phrase in phrases:
        if not phrase:
            continue
        for field_name, field_value in normalized_fields.items():
            if field_value and phrase in field_value:
                score += float(index.bonuses.get("phrase", 0.0))
                matched_fields.add(field_name)

    if node.is_leaf:
        score += float(index.bonuses.get("leaf", 0.0))

    if query_terms and all(term in matched_terms for term in query_terms):
        score += float(index.bonuses.get("all_terms_hit", 0.0))

    return score, sorted(matched_terms), sorted(matched_fields)
