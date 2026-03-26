from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CorpusDocumentRecord:
    doc_id: str
    doc_name: str
    source_path: str
    doc_type: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    created_at: str = ""
    query_index_path: str = ""


@dataclass(slots=True)
class CorpusQueryRequest:
    query: str
    top_k: int = 10
    doc_id: str | None = None
    doc_type: str | None = None
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    created_at_from: str | None = None
    created_at_to: str | None = None
    leaf_only: bool = False
    rerank_with_llm: bool = False
    debug_explain: bool = False


@dataclass(slots=True)
class CorpusQueryResult:
    doc_id: str
    doc_name: str
    doc_type: str
    tags: list[str]
    source: str
    created_at: str
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
            "doc_name": self.doc_name,
            "doc_type": self.doc_type,
            "tags": list(self.tags),
            "source": self.source,
            "created_at": self.created_at,
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
class CorpusIndexArtifact:
    corpus_name: str
    documents: list[CorpusDocumentRecord]
    doc_id_to_record: dict[str, CorpusDocumentRecord]
    doc_id_to_index_path: dict[str, str]
    metadata_catalog: dict[str, Any]
    exclude_globs: list[str] = field(default_factory=list)
    version: str = "1"
