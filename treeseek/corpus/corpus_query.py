from __future__ import annotations

from datetime import datetime

from .corpus_models import CorpusIndexArtifact, CorpusQueryRequest, CorpusQueryResult
from .. import load_query_index, rerank_query_results, search_index


def _record_matches_filters(record, request: CorpusQueryRequest) -> bool:
    if request.doc_id and record.doc_id != request.doc_id:
        return False
    if request.doc_type and record.doc_type != request.doc_type:
        return False
    if request.source and record.source != request.source:
        return False
    if request.tags:
        if not set(request.tags).intersection(record.tags):
            return False

    if request.created_at_from or request.created_at_to:
        try:
            record_dt = datetime.fromisoformat(record.created_at)
        except Exception:
            return False
        if request.created_at_from and record_dt < datetime.fromisoformat(request.created_at_from):
            return False
        if request.created_at_to and record_dt > datetime.fromisoformat(request.created_at_to):
            return False
    return True


def search_corpus(
    corpus_index: CorpusIndexArtifact,
    request: CorpusQueryRequest,
    *,
    model: str | None = None,
) -> list[CorpusQueryResult]:
    candidate_records = [record for record in corpus_index.documents if _record_matches_filters(record, request)]
    results: list[CorpusQueryResult] = []

    for record in candidate_records:
        query_index = load_query_index(record.query_index_path)
        doc_results = search_index(
            query_index,
            request.query,
            top_k=request.top_k,
            leaf_only=request.leaf_only,
            debug_explain=request.debug_explain,
        )
        if request.rerank_with_llm:
            doc_results = rerank_query_results(query_index, request.query, doc_results, model=model)

        for result in doc_results:
            results.append(
                CorpusQueryResult(
                    doc_id=record.doc_id,
                    doc_name=record.doc_name,
                    doc_type=record.doc_type,
                    tags=list(record.tags),
                    source=record.source,
                    created_at=record.created_at,
                    node_id=result.node_id,
                    title=result.title,
                    start_index=result.start_index,
                    end_index=result.end_index,
                    score=result.score,
                    matched_terms=list(result.matched_terms),
                    matched_fields=list(result.matched_fields),
                    ancestor_ids=list(result.ancestor_ids),
                    summary=result.summary,
                    snippet=result.snippet,
                    highlight_terms=list(result.highlight_terms),
                    snippet_field=result.snippet_field,
                    field_scores=result.field_scores,
                    bonuses_applied=list(result.bonuses_applied),
                    phrase_matches=result.phrase_matches,
                )
            )

    results.sort(key=lambda item: (-item.score, item.doc_id, item.start_index))
    return results[: request.top_k]
