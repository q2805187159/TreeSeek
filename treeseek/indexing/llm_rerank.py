from __future__ import annotations

import os

from .models import QueryIndexArtifact, QueryResult
from ..utils import extract_json, llm_completion


def rerank_query_results(
    index: QueryIndexArtifact,
    query: str,
    results: list[QueryResult],
    *,
    model: str | None = None,
    top_k: int | None = None,
) -> list[QueryResult]:
    if not results:
        return []

    limit = top_k or len(results)
    candidates = results[:limit]
    model_name = model or os.getenv("MODEL")
    if not model_name:
        raise ValueError("MODEL environment variable or model argument is required for LLM rerank")

    candidate_payload = []
    for result in candidates:
        node = index.nodes[index.node_id_to_idx[result.node_id]]
        candidate_payload.append(
            {
                "node_id": result.node_id,
                "title": result.title,
                "start_index": result.start_index,
                "end_index": result.end_index,
                "summary": result.summary,
                "path_titles": node.path_titles,
            }
        )

    prompt = f"""
You are given a user query and a list of candidate document nodes.
Re-rank the candidates from most relevant to least relevant for answering the query.

Query: {query}

Candidates:
{candidate_payload}

Return JSON only with this schema:
{{
  "thinking": "<brief reasoning>",
  "ranked_node_ids": ["node_id_1", "node_id_2"]
}}
"""

    response = llm_completion(model=model_name, prompt=prompt)
    json_response = extract_json(response)
    ranked_node_ids = json_response.get("ranked_node_ids") or []

    if not ranked_node_ids:
        return list(results)

    result_by_id = {result.node_id: result for result in candidates}
    reranked: list[QueryResult] = []
    seen = set()
    for node_id in ranked_node_ids:
        if node_id in result_by_id and node_id not in seen:
            reranked.append(result_by_id[node_id])
            seen.add(node_id)

    reranked.extend(result for result in candidates if result.node_id not in seen)
    reranked.extend(results[limit:])
    return reranked
