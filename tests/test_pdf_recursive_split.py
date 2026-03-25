import asyncio
from types import SimpleNamespace

import pymupdf

from treeseek.pdf_tree import process_large_node_recursively_with_depth


def test_heuristic_recursive_split_creates_child_nodes(local_tmp_path, monkeypatch):
    pdf_path = local_tmp_path / "split_demo.pdf"

    doc = pymupdf.open()
    pages = [
        "1.1 Overview\nThe retrieval system uses deterministic candidate generation.\n",
        "1.2 Background\nObservability and logging are key for evaluation.\n",
        "1.3 Implementation Details\nThe hybrid index combines titles and summaries.\n",
        "1.4 Testing Notes\nBenchmarks measure build and query latency.\n",
    ]
    for content in pages:
        page = doc.new_page()
        page.insert_text((72, 72), content, fontsize=12)
    doc.save(pdf_path)
    doc.close()

    doc = pymupdf.open(pdf_path)
    page_list = [(page.get_text(), max(1, len(page.get_text().split()))) for page in doc]
    doc.close()
    node = {
        "title": "Main Section",
        "start_index": 1,
        "end_index": 4,
    }

    def unexpected_meta_processor(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("heuristic split should avoid LLM fallback for this test")

    monkeypatch.setattr("treeseek.pdf_tree.meta_processor", unexpected_meta_processor)

    opt = SimpleNamespace(
        model=None,
        max_page_num_each_node=999,
        max_token_num_each_node=999999,
        recursive_split_enabled="yes",
        recursive_split_min_pages=2,
        recursive_split_min_tokens=1,
        recursive_split_max_depth=3,
        recursive_split_heading_patterns=[r"^\d+\.\d+", r"^[A-Z][A-Za-z\s\-/]{3,}$"],
    )

    result = asyncio.run(process_large_node_recursively_with_depth(node, page_list, opt=opt, logger=None, current_depth=1))

    assert "nodes" in result
    assert len(result["nodes"]) >= 2
    start_indexes = [child["start_index"] for child in result["nodes"]]
    assert start_indexes == sorted(start_indexes)
    assert all(child["end_index"] >= child["start_index"] for child in result["nodes"])
