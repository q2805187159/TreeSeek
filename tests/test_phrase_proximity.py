from treeseek.indexing.builder import build_query_index
from treeseek.indexing.query_engine import search_index


def test_exact_phrase_match_beats_scattered_terms():
    doc = {
        "doc_name": "phrase-demo",
        "structure": [
            {
                "title": "Exact Phrase",
                "node_id": "3001",
                "start_index": 1,
                "end_index": 1,
                "text": "The retrieval design workflow narrows candidates early.",
            },
            {
                "title": "Scattered Terms",
                "node_id": "3002",
                "start_index": 2,
                "end_index": 2,
                "text": "Retrieval systems can become complex when many pages intervene before the final design choices are documented.",
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "\"retrieval design\"", top_k=2, debug_explain=True)

    assert results
    assert results[0].node_id == "3001"
    assert results[0].phrase_matches
    assert results[0].bonuses_applied


def test_unquoted_multi_term_query_does_not_trigger_phrase_bonus():
    doc = {
        "doc_name": "plain-query-demo",
        "structure": [
            {
                "title": "Exact Phrase",
                "node_id": "3051",
                "start_index": 1,
                "end_index": 1,
                "text": "The retrieval design workflow narrows candidates early.",
            },
            {
                "title": "Near Terms",
                "node_id": "3052",
                "start_index": 2,
                "end_index": 2,
                "text": "Retrieval metrics and design reviews are documented together.",
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "retrieval design", top_k=2, debug_explain=True)

    assert results
    assert all(
        all(item["name"] != "phrase" for item in result.bonuses_applied)
        for result in results
    )


def test_proximity_bonus_prefers_nearer_terms():
    doc = {
        "doc_name": "proximity-demo",
        "structure": [
            {
                "title": "Near Terms",
                "node_id": "3101",
                "start_index": 1,
                "end_index": 1,
                "text": "Retrieval metrics and design reviews are documented together.",
            },
            {
                "title": "Far Terms",
                "node_id": "3102",
                "start_index": 2,
                "end_index": 2,
                "text": "Retrieval logs cover many operational details before unrelated architecture notes and eventually design decisions are discussed much later.",
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "retrieval design", top_k=2, debug_explain=True)

    assert results
    assert results[0].node_id == "3101"
    assert any(item["name"] == "proximity" for item in results[0].bonuses_applied)
