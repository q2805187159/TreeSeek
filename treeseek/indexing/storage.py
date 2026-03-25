from __future__ import annotations

import gzip
import pickle

from .models import QueryIndexArtifact


def ensure_query_index_compat(index: QueryIndexArtifact) -> QueryIndexArtifact:
    if not hasattr(index, "snippet_max_chars") or not getattr(index, "snippet_max_chars", 0):
        index.snippet_max_chars = 320
    if not hasattr(index, "snippet_context_chars") or not getattr(index, "snippet_context_chars", 0):
        index.snippet_context_chars = 120
    if not hasattr(index, "document_count") or not getattr(index, "document_count", 0):
        index.document_count = len(getattr(index, "nodes", []) or [])
    if not hasattr(index, "document_frequencies") or getattr(index, "document_frequencies", None) is None:
        index.document_frequencies = {}
    if not hasattr(index, "average_field_lengths") or getattr(index, "average_field_lengths", None) is None:
        index.average_field_lengths = {}
    if not hasattr(index, "field_lengths") or getattr(index, "field_lengths", None) is None:
        index.field_lengths = {}
    if not hasattr(index, "field_term_positions") or getattr(index, "field_term_positions", None) is None:
        index.field_term_positions = {}
    if not hasattr(index, "debug_explain_default") or getattr(index, "debug_explain_default", None) is None:
        index.debug_explain_default = False
    if not hasattr(index, "bm25_k1") or not getattr(index, "bm25_k1", 0):
        index.bm25_k1 = 1.2
    if not hasattr(index, "bm25_b") or not getattr(index, "bm25_b", 0):
        index.bm25_b = 0.75
    if not hasattr(index, "proximity_window") or not getattr(index, "proximity_window", 0):
        index.proximity_window = 12
    if not hasattr(index, "diversity_penalty") or not getattr(index, "diversity_penalty", 0):
        index.diversity_penalty = 0.75
    return index


def save_query_index(index: QueryIndexArtifact, path: str) -> str:
    with gzip.open(path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_query_index(path: str) -> QueryIndexArtifact:
    with gzip.open(path, "rb") as f:
        return ensure_query_index_compat(pickle.load(f))
