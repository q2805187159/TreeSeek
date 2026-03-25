from __future__ import annotations

import re

from .normalizer import normalize_text

FIELD_PRIORITY = ("text", "summary", "prefix_summary", "title")
FALLBACK_SNIPPET_CHARS = 280


def _compact_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _truncate_snippet(text: str, hit_index: int | None, *, max_chars: int, context_chars: int) -> str:
    if not text:
        return ""
    if hit_index is None:
        snippet = text[: min(FALLBACK_SNIPPET_CHARS, max_chars)].strip()
        return snippet if len(text) <= len(snippet) else f"{snippet}..."

    start = max(0, hit_index - context_chars)
    end = min(len(text), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)

    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(text):
        snippet = f"{snippet}..."
    return snippet


def build_result_snippet(node, query_terms: list[str], *, max_chars: int = 320, context_chars: int = 120):
    deduped_terms = list(dict.fromkeys(term for term in query_terms if term))
    best_result = None
    fallback_result = None

    for field_name in FIELD_PRIORITY:
        raw_value = getattr(node, field_name, None)
        compact_value = _compact_text(raw_value)
        if not compact_value:
            continue

        if fallback_result is None:
            fallback_result = (
                _truncate_snippet(compact_value, None, max_chars=max_chars, context_chars=context_chars),
                [],
                field_name,
            )

        lowered_value = compact_value.lower()
        matched_terms = [term for term in deduped_terms if normalize_text(term) and normalize_text(term) in lowered_value]
        if not matched_terms:
            continue

        hit_positions = [lowered_value.index(normalize_text(term)) for term in matched_terms]
        earliest_hit = min(hit_positions)
        snippet = _truncate_snippet(compact_value, earliest_hit, max_chars=max_chars, context_chars=context_chars)
        snippet_lower = snippet.lower()
        highlight_terms = [term for term in deduped_terms if normalize_text(term) in snippet_lower]

        candidate = (
            len(set(matched_terms)),
            -FIELD_PRIORITY.index(field_name),
            snippet,
            highlight_terms,
            field_name,
        )
        if best_result is None or candidate[:2] > best_result[:2]:
            best_result = candidate

    if best_result is not None:
        return best_result[2], best_result[3], best_result[4]

    if fallback_result is not None:
        return fallback_result

    return None, [], None
