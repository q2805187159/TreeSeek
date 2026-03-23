from rag.indexing.builder import build_query_index
from rag.indexing.query_engine import search_index
from rag.indexing.storage import load_query_index, save_query_index


def test_save_and_load_round_trip(annual_report_doc, local_tmp_path):
    index = build_query_index(annual_report_doc, include_text=False)
    path = local_tmp_path / "annual_query_index.pkl.gz"

    save_query_index(index, str(path))
    loaded = load_query_index(str(path))

    original = [item.to_dict() for item in search_index(index, "financial stability", top_k=3)]
    restored = [item.to_dict() for item in search_index(loaded, "financial stability", top_k=3)]
    assert path.exists()
    assert restored == original
