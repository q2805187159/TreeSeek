from __future__ import annotations

from bisect import bisect_left
from typing import Iterable, Protocol

try:
    from pyroaring import BitMap as RoaringBitmap

    HAVE_PYROARING = True
except Exception:  # pragma: no cover - exercised in fallback tests
    RoaringBitmap = None
    HAVE_PYROARING = False


class PostingListProtocol(Protocol):
    def add(self, value: int) -> None: ...

    def update(self, values: Iterable[int]) -> None: ...

    def union(self, other: "PostingListProtocol") -> "PostingListProtocol": ...

    def intersection(self, other: "PostingListProtocol") -> "PostingListProtocol": ...

    def difference(self, other: "PostingListProtocol") -> "PostingListProtocol": ...

    def to_list(self) -> list[int]: ...

    def __len__(self) -> int: ...


class SortedPostingList:
    def __init__(self, values: Iterable[int] | None = None):
        self._values = sorted(set(int(value) for value in (values or [])))

    def add(self, value: int) -> None:
        value = int(value)
        idx = bisect_left(self._values, value)
        if idx >= len(self._values) or self._values[idx] != value:
            self._values.insert(idx, value)

    def update(self, values: Iterable[int]) -> None:
        self._values = sorted(set(self._values).union(int(value) for value in values))

    def union(self, other: PostingListProtocol) -> "SortedPostingList":
        return SortedPostingList(set(self._values).union(other.to_list()))

    def intersection(self, other: PostingListProtocol) -> "SortedPostingList":
        return SortedPostingList(set(self._values).intersection(other.to_list()))

    def difference(self, other: PostingListProtocol) -> "SortedPostingList":
        return SortedPostingList(set(self._values).difference(other.to_list()))

    def to_list(self) -> list[int]:
        return list(self._values)

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class BitmapPostingList:
    def __init__(self, values: Iterable[int] | None = None):
        if not HAVE_PYROARING:
            raise ImportError("pyroaring is required for BitmapPostingList")
        self._bitmap = RoaringBitmap(int(value) for value in (values or []))

    @classmethod
    def from_bitmap(cls, bitmap) -> "BitmapPostingList":
        instance = cls()
        instance._bitmap = bitmap
        return instance

    def add(self, value: int) -> None:
        self._bitmap.add(int(value))

    def update(self, values: Iterable[int]) -> None:
        self._bitmap.update(int(value) for value in values)

    def union(self, other: PostingListProtocol) -> "BitmapPostingList":
        if isinstance(other, BitmapPostingList):
            return BitmapPostingList.from_bitmap(self._bitmap | other._bitmap)
        return BitmapPostingList(self.to_list()).union(BitmapPostingList(other.to_list()))

    def intersection(self, other: PostingListProtocol) -> "BitmapPostingList":
        if isinstance(other, BitmapPostingList):
            return BitmapPostingList.from_bitmap(self._bitmap & other._bitmap)
        return BitmapPostingList(self.to_list()).intersection(BitmapPostingList(other.to_list()))

    def difference(self, other: PostingListProtocol) -> "BitmapPostingList":
        if isinstance(other, BitmapPostingList):
            return BitmapPostingList.from_bitmap(self._bitmap - other._bitmap)
        return BitmapPostingList(self.to_list()).difference(BitmapPostingList(other.to_list()))

    def to_list(self) -> list[int]:
        return list(self._bitmap)

    def __iter__(self):
        return iter(self._bitmap)

    def __len__(self) -> int:
        return len(self._bitmap)


def resolve_postings_backend(backend: str | None = None) -> str:
    if backend == "sorted":
        return "sorted"
    if backend == "bitmap" and HAVE_PYROARING:
        return "bitmap"
    return "sorted"


def create_posting_list(
    values: Iterable[int] | None = None,
    backend: str | None = None,
) -> PostingListProtocol:
    resolved_backend = resolve_postings_backend(backend)
    if resolved_backend == "bitmap":
        return BitmapPostingList(values)
    return SortedPostingList(values)
