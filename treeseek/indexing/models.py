from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IndexedNode:
    doc_id: str
    node_id: str
    title: str
    summary: str | None = None
    prefix_summary: str | None = None
    text: str | None = None
    start_index: int = 0
    end_index: int = 0
    depth: int = 1
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)
    path_titles: list[str] = field(default_factory=list)
    is_leaf: bool = False
    token_count: int = 0


@dataclass(slots=True)
class QueryRequest:
    query: str
    top_k: int = 10
    expand_ancestors: int = 1
    leaf_only: bool = False
    depth: int | None = None
    min_page: int | None = None
    max_page: int | None = None
    debug_explain: bool = False


@dataclass(slots=True)
class QueryResult:
    doc_id: str
    node_id: str
    title: str
    start_index: int
    end_index: int
    score: float
    matched_terms: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)
    ancestor_ids: list[str] = field(default_factory=list)
    summary: str | None = None
    snippet: str | None = None
    highlight_terms: list[str] = field(default_factory=list)
    snippet_field: str | None = None
    field_scores: dict[str, float] | None = None
    bonuses_applied: list[dict[str, float | str]] = field(default_factory=list)
    phrase_matches: dict[str, list[str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "doc_id": self.doc_id,
            "node_id": self.node_id,
            "title": self.title,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "matched_fields": list(self.matched_fields),
            "ancestor_ids": list(self.ancestor_ids),
            "summary": self.summary,
            "snippet": self.snippet,
            "highlight_terms": list(self.highlight_terms),
            "snippet_field": self.snippet_field,
        }
        if self.field_scores:
            payload["field_scores"] = dict(self.field_scores)
        if self.bonuses_applied:
            payload["bonuses_applied"] = list(self.bonuses_applied)
        if self.phrase_matches:
            payload["phrase_matches"] = dict(self.phrase_matches)
        return payload


@dataclass
class QueryIndexArtifact:
    doc_id: str
    nodes: list[IndexedNode]
    node_id_to_idx: dict[str, int]
    normalized_title_to_ids: dict[str, list[str]]
    parent_map: dict[str, str | None]
    children_map: dict[str, list[str]]
    title_terms: dict[str, Any]
    summary_terms: dict[str, Any]
    prefix_summary_terms: dict[str, Any]
    path_terms: dict[str, Any]
    text_terms: dict[str, Any]
    depth_filter: dict[int, Any]
    leaf_filter: dict[bool, Any]
    page_filter: dict[int, Any]
    field_term_frequencies: dict[int, dict[str, dict[str, int]]] = field(default_factory=dict)
    normalized_fields: dict[int, dict[str, str]] = field(default_factory=dict)
    field_weights: dict[str, float] = field(default_factory=dict)
    bonuses: dict[str, float] = field(default_factory=dict)
    postings_backend: str = "sorted"
    include_text: bool = False
    snippet_max_chars: int = 320
    snippet_context_chars: int = 120
    document_count: int = 0
    document_frequencies: dict[str, dict[str, int]] = field(default_factory=dict)
    average_field_lengths: dict[str, float] = field(default_factory=dict)
    field_lengths: dict[int, dict[str, int]] = field(default_factory=dict)
    field_term_positions: dict[int, dict[str, dict[str, list[int]]]] = field(default_factory=dict)
    debug_explain_default: bool = False
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    proximity_window: int = 12
    diversity_penalty: float = 0.75
