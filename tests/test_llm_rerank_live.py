from __future__ import annotations

import os

import pytest

from rag.indexing.builder import build_query_index
from rag.indexing.llm_rerank import rerank_query_results
from rag.indexing.query_engine import search_index


@pytest.mark.live_llm
def test_live_llm_rerank_smoke(earnings_doc):
    if not (os.getenv("MODEL") and (os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")) and (os.getenv("API_URL") or os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL"))):
        pytest.skip("MODEL/API credentials are required for live LLM rerank")

    index = build_query_index(earnings_doc, include_text=False)
    results = search_index(index, "Disney+ subscribers", top_k=3)
    reranked = rerank_query_results(index, "Disney+ subscribers", results, top_k=3)

    assert reranked
    assert len(reranked) == len(results)
    assert {result.node_id for result in reranked} == {result.node_id for result in results}
    assert all(result.score >= 0 for result in reranked)
