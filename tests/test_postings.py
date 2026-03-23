from rag.indexing import postings


def test_sorted_posting_list_set_operations():
    left = postings.SortedPostingList([1, 2, 4])
    right = postings.SortedPostingList([2, 3, 4])

    assert left.union(right).to_list() == [1, 2, 3, 4]
    assert left.intersection(right).to_list() == [2, 4]
    assert left.difference(right).to_list() == [1]


def test_bitmap_backend_falls_back_when_unavailable(monkeypatch):
    monkeypatch.setattr(postings, "HAVE_PYROARING", False)
    posting = postings.create_posting_list([1, 2, 3], backend="bitmap")
    assert isinstance(posting, postings.SortedPostingList)


def test_bitmap_and_sorted_results_match_when_available():
    if not postings.HAVE_PYROARING:
        return

    left_bitmap = postings.BitmapPostingList([1, 2, 4])
    right_bitmap = postings.BitmapPostingList([2, 3, 4])
    left_sorted = postings.SortedPostingList([1, 2, 4])
    right_sorted = postings.SortedPostingList([2, 3, 4])

    assert left_bitmap.union(right_bitmap).to_list() == left_sorted.union(right_sorted).to_list()
    assert left_bitmap.intersection(right_bitmap).to_list() == left_sorted.intersection(right_sorted).to_list()
    assert left_bitmap.difference(right_bitmap).to_list() == left_sorted.difference(right_sorted).to_list()
