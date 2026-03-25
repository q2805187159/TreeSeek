from __future__ import annotations

import math

from .models import QueryIndexArtifact


def _bm25_field_score(index: QueryIndexArtifact, *, field_name: str, term: str, tf: int, field_length: int) -> float:
    if tf <= 0:
        return 0.0

    field_weight = float(index.field_weights.get(field_name, 0.0))
    if field_weight <= 0:
        return 0.0

    document_count = max(int(getattr(index, "document_count", 0) or len(index.nodes) or 1), 1)
    document_frequencies = getattr(index, "document_frequencies", {}).get(field_name, {})
    df = int(document_frequencies.get(term, 0))
    avg_field_length = float(getattr(index, "average_field_lengths", {}).get(field_name, 0.0) or 1.0)
    field_length = max(field_length, 1)

    idf = math.log(1 + ((document_count - df + 0.5) / (df + 0.5)))
    k1 = float(getattr(index, "bm25_k1", 1.2))
    b = float(getattr(index, "bm25_b", 0.75))
    tf_norm = ((k1 + 1) * tf) / (k1 * (1 - b + b * (field_length / avg_field_length)) + tf)
    return field_weight * idf * tf_norm


def _get_min_gap(left_positions: list[int], right_positions: list[int]) -> int | None:
    if not left_positions or not right_positions:
        return None
    best = None
    for left in left_positions:
        for right in right_positions:
            gap = abs(right - left)
            if best is None or gap < best:
                best = gap
    return best


def score_candidate(
    index: QueryIndexArtifact,
    node_idx: int,
    query_terms: list[str],
    phrases: list[str],
    normalized_query: str,
    query_node_id: str | None = None,
    *,
    debug_explain: bool = False,
):
    node = index.nodes[node_idx]
    field_terms = index.field_term_frequencies.get(node_idx, {})
    normalized_fields = index.normalized_fields.get(node_idx, {})
    field_lengths = getattr(index, "field_lengths", {}).get(node_idx, {})
    field_positions = getattr(index, "field_term_positions", {}).get(node_idx, {})

    score = 0.0
    matched_terms: set[str] = set()
    matched_fields: set[str] = set()
    field_scores: dict[str, float] = {}
    bonuses_applied: list[dict[str, float | str]] = []
    phrase_matches: dict[str, list[str]] = {}

    for field_name, term_counts in field_terms.items():
        current_field_score = 0.0
        field_length = int(field_lengths.get(field_name, 0))
        for term in query_terms:
            tf = int(term_counts.get(term, 0))
            if tf <= 0:
                continue
            contribution = _bm25_field_score(
                index,
                field_name=field_name,
                term=term,
                tf=tf,
                field_length=field_length,
            )
            if contribution:
                current_field_score += contribution
                matched_terms.add(term)
                matched_fields.add(field_name)

        if current_field_score:
            score += current_field_score
            if debug_explain:
                field_scores[field_name] = round(current_field_score, 6)

    exact_title_targets = []
    if normalized_query:
        exact_title_targets.append(normalized_query)
    for phrase in phrases:
        if phrase:
            exact_title_targets.append(phrase)
    exact_title_targets = list(dict.fromkeys(exact_title_targets))

    if normalized_fields.get("title") in exact_title_targets:
        exact_bonus = float(index.bonuses.get("exact_title", 0.0))
        score += exact_bonus
        matched_fields.add("title")
        if debug_explain and exact_bonus:
            bonuses_applied.append({"name": "exact_title", "value": round(exact_bonus, 6), "field": "title"})

    if query_node_id and node.node_id == query_node_id:
        node_id_bonus = float(index.bonuses.get("exact_title", 0.0))
        score += node_id_bonus
        matched_fields.add("title")
        if debug_explain and node_id_bonus:
            bonuses_applied.append({"name": "node_id_exact", "value": round(node_id_bonus, 6), "field": "title"})

    for phrase in phrases:
        if not phrase:
            continue
        for field_name, field_value in normalized_fields.items():
            if field_value and phrase in field_value:
                phrase_bonus = float(index.bonuses.get("phrase", 0.0))
                score += phrase_bonus
                matched_fields.add(field_name)
                if debug_explain:
                    phrase_matches.setdefault(field_name, []).append(phrase)
                    if phrase_bonus:
                        bonuses_applied.append(
                            {"name": "phrase", "value": round(phrase_bonus, 6), "field": field_name, "phrase": phrase}
                        )

    proximity_best = 0.0
    proximity_field = None
    proximity_pair = None
    if len(query_terms) >= 2:
        for field_name, term_positions in field_positions.items():
            best_for_field = 0.0
            best_pair = None
            for left_term, right_term in zip(query_terms, query_terms[1:]):
                min_gap = _get_min_gap(term_positions.get(left_term, []), term_positions.get(right_term, []))
                if min_gap is None:
                    continue
                if min_gap <= int(getattr(index, "proximity_window", 12)):
                    bonus = float(index.bonuses.get("proximity", 0.0) or 0.0) * (1 / (1 + min_gap))
                    if bonus > best_for_field:
                        best_for_field = bonus
                        best_pair = f"{left_term}|{right_term}"
            if best_for_field > proximity_best:
                proximity_best = best_for_field
                proximity_field = field_name
                proximity_pair = best_pair

    if proximity_best:
        score += proximity_best
        if debug_explain:
            bonuses_applied.append(
                {
                    "name": "proximity",
                    "value": round(proximity_best, 6),
                    "field": proximity_field or "",
                    "pair": proximity_pair or "",
                }
            )

    if node.is_leaf:
        leaf_bonus = float(index.bonuses.get("leaf", 0.0))
        score += leaf_bonus
        if debug_explain and leaf_bonus:
            bonuses_applied.append({"name": "leaf", "value": round(leaf_bonus, 6), "field": "node"})

    if query_terms and all(term in matched_terms for term in query_terms):
        all_terms_bonus = float(index.bonuses.get("all_terms_hit", 0.0))
        score += all_terms_bonus
        if debug_explain and all_terms_bonus:
            bonuses_applied.append({"name": "all_terms_hit", "value": round(all_terms_bonus, 6), "field": "node"})

    return {
        "raw_score": score,
        "matched_terms": sorted(matched_terms),
        "matched_fields": sorted(matched_fields),
        "field_scores": {field: round(value, 6) for field, value in field_scores.items()} if debug_explain else None,
        "bonuses_applied": bonuses_applied if debug_explain else [],
        "phrase_matches": phrase_matches if debug_explain and phrase_matches else None,
    }
