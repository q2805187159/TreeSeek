from treeseek.indexing.builder import build_query_index
from treeseek.indexing.query_engine import search_index


def test_snippet_prefers_text_for_leaf_text_matches(synthetic_text_doc):
    index = build_query_index(synthetic_text_doc, include_text=True)
    results = search_index(index, "direct-to-consumer subscriber growth", top_k=1, leaf_only=True)

    assert results
    result = results[0]
    assert result.snippet_field == "text"
    assert result.snippet is not None
    assert "subscriber growth" in result.snippet.lower()
    assert {"direct-to-consumer", "subscriber", "growth"}.intersection(result.highlight_terms)


def test_snippet_falls_back_to_summary_when_text_not_indexed(annual_report_doc):
    index = build_query_index(annual_report_doc, include_text=False)
    results = search_index(index, "financial stability", top_k=1)

    assert results
    result = results[0]
    assert result.snippet is not None
    assert result.snippet_field in {"summary", "title"}
    assert result.highlight_terms
