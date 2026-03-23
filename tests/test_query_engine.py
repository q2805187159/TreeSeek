import json

from rag.indexing.builder import build_query_index
from rag.indexing.query_engine import search_index


def test_exact_title_query_hits_expected_node(annual_report_doc):
    index = build_query_index(annual_report_doc, include_text=False)
    results = search_index(index, "Financial Stability", top_k=3)

    assert results
    assert results[0].node_id == "0006"
    assert "title" in results[0].matched_fields


def test_summary_query_uses_summary_terms(earnings_doc):
    index = build_query_index(earnings_doc, include_text=False)
    results = search_index(index, "Disney+ subscribers", top_k=5)

    returned_ids = {result.node_id for result in results}
    assert returned_ids.intersection({"0003", "0014", "0001"})


def test_leaf_text_query_and_leaf_only_filter(synthetic_text_doc):
    index = build_query_index(synthetic_text_doc, include_text=True)
    results = search_index(index, "direct-to-consumer subscriber growth", top_k=3, leaf_only=True)

    assert results
    assert results[0].node_id == "1001"
    assert results[0].ancestor_ids == ["1000"]


def test_node_id_and_page_filters(annual_report_doc):
    index = build_query_index(annual_report_doc, include_text=False)
    node_id_results = search_index(index, "0008", top_k=3)
    page_results = search_index(index, "cooperation", top_k=3, min_page=28, max_page=31)

    assert node_id_results and node_id_results[0].node_id == "0008"
    assert page_results and page_results[0].start_index <= 31


def test_query_cases_cover_expected_ids(query_cases):
    for case in query_cases:
        with open(f"tests/results/{case['doc']}", "r", encoding="utf-8") as f:
            doc = json.load(f)
        index = build_query_index(doc, include_text=False)
        results = search_index(index, case["query"], top_k=5)
        returned_ids = {result.node_id for result in results}
        assert returned_ids.intersection(set(case["expected_node_ids"]))
