from treeseek.indexing.builder import build_query_index
from treeseek.indexing.query_engine import search_index
from treeseek.indexing.storage import load_query_index, save_query_index


def test_save_and_load_round_trip(annual_report_doc, local_tmp_path):
    index = build_query_index(annual_report_doc, include_text=False)
    path = local_tmp_path / "annual_query_index.pkl.gz"

    save_query_index(index, str(path))
    loaded = load_query_index(str(path))

    original = [item.to_dict() for item in search_index(index, "financial stability", top_k=3)]
    restored = [item.to_dict() for item in search_index(loaded, "financial stability", top_k=3)]
    assert path.exists()
    assert restored == original


def test_load_query_index_backfills_missing_v2_fields(annual_report_doc, local_tmp_path):
    index = build_query_index(annual_report_doc, include_text=False)
    for attr in [
        "document_count",
        "document_frequencies",
        "average_field_lengths",
        "field_lengths",
        "field_term_positions",
        "debug_explain_default",
        "bm25_k1",
        "bm25_b",
        "proximity_window",
        "diversity_penalty",
    ]:
        if hasattr(index, attr):
            delattr(index, attr)

    path = local_tmp_path / "legacy_query_index.pkl.gz"
    save_query_index(index, str(path))
    loaded = load_query_index(str(path))

    assert loaded.document_count
    assert isinstance(loaded.document_frequencies, dict)
    assert isinstance(loaded.average_field_lengths, dict)
    assert isinstance(loaded.field_lengths, dict)
    assert isinstance(loaded.field_term_positions, dict)
    assert loaded.bm25_k1 == 1.2
    assert loaded.bm25_b == 0.75
    assert loaded.proximity_window == 12
    assert loaded.diversity_penalty == 0.75
