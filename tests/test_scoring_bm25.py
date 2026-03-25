from treeseek.indexing.builder import build_query_index
from treeseek.indexing.query_engine import search_index


def test_bm25_lite_prefers_title_match_over_repeated_text():
    doc = {
        "doc_name": "bm25-demo",
        "structure": [
            {
                "title": "Liquidity Management",
                "node_id": "2001",
                "start_index": 1,
                "end_index": 1,
                "summary": "Liquidity management approach for treasury operations.",
                "text": "Liquidity planning and treasury operations overview.",
            },
            {
                "title": "Appendix",
                "node_id": "2002",
                "start_index": 2,
                "end_index": 2,
                "summary": "Repeated operational notes.",
                "text": "liquidity liquidity liquidity liquidity liquidity liquidity",
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "liquidity management", top_k=2, debug_explain=True)

    assert results
    assert results[0].node_id == "2001"
    assert results[0].field_scores
    assert "title" in results[0].field_scores
