from rag.indexing.builder import build_query_index, flatten_tree


def test_flatten_tree_preserves_parent_child_relationships(annual_report_doc):
    nodes = flatten_tree(annual_report_doc)
    by_id = {node.node_id: node for node in nodes}

    assert by_id["0006"].child_ids == ["0007", "0008"]
    assert by_id["0007"].parent_id == "0006"
    assert by_id["0007"].depth == 2


def test_build_query_index_creates_title_and_page_filters(annual_report_doc):
    index = build_query_index(annual_report_doc, include_text=False)

    assert len(index.nodes) == 76
    assert "financial" in index.title_terms
    assert 21 in index.page_filter
    assert True in index.leaf_filter
    assert "0006" in index.normalized_title_to_ids["financial stability"]
