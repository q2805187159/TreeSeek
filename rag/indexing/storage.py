from __future__ import annotations

import gzip
import pickle

from .models import QueryIndexArtifact


def save_query_index(index: QueryIndexArtifact, path: str) -> str:
    with gzip.open(path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_query_index(path: str) -> QueryIndexArtifact:
    with gzip.open(path, "rb") as f:
        return pickle.load(f)
