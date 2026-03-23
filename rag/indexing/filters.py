from __future__ import annotations

from .models import QueryIndexArtifact
from .postings import create_posting_list


def _union_page_filters(index: QueryIndexArtifact, min_page: int, max_page: int):
    combined = create_posting_list(backend=index.postings_backend)
    for page in range(min_page, max_page + 1):
        posting = index.page_filter.get(page)
        if posting is not None:
            combined = combined.union(posting)
    return combined


def apply_filters(
    index: QueryIndexArtifact,
    posting,
    *,
    leaf_only: bool = False,
    depth: int | None = None,
    min_page: int | None = None,
    max_page: int | None = None,
):
    filtered = posting
    if leaf_only:
        leaf_posting = index.leaf_filter.get(True)
        if leaf_posting is None:
            return create_posting_list(backend=index.postings_backend)
        filtered = filtered.intersection(leaf_posting)

    if depth is not None:
        depth_posting = index.depth_filter.get(depth)
        if depth_posting is None:
            return create_posting_list(backend=index.postings_backend)
        filtered = filtered.intersection(depth_posting)

    if min_page is not None or max_page is not None:
        min_value = min_page if min_page is not None else max_page
        max_value = max_page if max_page is not None else min_page
        if min_value is None or max_value is None:
            return create_posting_list(backend=index.postings_backend)
        page_posting = _union_page_filters(index, min_value, max_value)
        filtered = filtered.intersection(page_posting)

    return filtered
