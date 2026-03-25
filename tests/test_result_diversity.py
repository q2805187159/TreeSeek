from treeseek.indexing.builder import build_query_index
from treeseek.indexing.query_engine import search_index


def test_duplicate_summaries_are_deduplicated():
    doc = {
        "doc_name": "dedupe-demo",
        "structure": [
            {
                "title": "Policy A",
                "node_id": "4001",
                "start_index": 1,
                "end_index": 1,
                "summary": "Compliance review process for high-risk cases.",
                "text": "Compliance review process for high-risk cases.",
            },
            {
                "title": "Policy B",
                "node_id": "4002",
                "start_index": 2,
                "end_index": 2,
                "summary": "Compliance review process for high-risk cases.",
                "text": "Compliance review process for high-risk cases.",
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "compliance review process", top_k=5)

    assert len(results) == 1


def test_diversity_prefers_different_parent_when_scores_are_close():
    doc = {
        "doc_name": "diversity-demo",
        "structure": [
            {
                "title": "Parent A",
                "node_id": "5000",
                "start_index": 1,
                "end_index": 2,
                "nodes": [
                    {
                        "title": "Sibling A1",
                        "node_id": "5001",
                        "start_index": 1,
                        "end_index": 1,
                        "text": "Compliance review workflow and control testing.",
                    },
                    {
                        "title": "Sibling A2",
                        "node_id": "5002",
                        "start_index": 2,
                        "end_index": 2,
                        "text": "Compliance review workflow and control testing.",
                    },
                ],
            },
            {
                "title": "Parent B",
                "node_id": "5100",
                "start_index": 3,
                "end_index": 3,
                "nodes": [
                    {
                        "title": "Sibling B1",
                        "node_id": "5101",
                        "start_index": 3,
                        "end_index": 3,
                        "text": "Compliance review workflow and controls.",
                    }
                ],
            },
        ],
    }

    index = build_query_index(doc, include_text=True)
    results = search_index(index, "compliance review workflow", top_k=2, debug_explain=True)

    returned_ids = [result.node_id for result in results]
    assert "5001" in returned_ids or "5002" in returned_ids
    assert "5101" in returned_ids
