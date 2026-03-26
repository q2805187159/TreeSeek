from __future__ import annotations

import gzip
import pickle

from .corpus_models import CorpusIndexArtifact


def save_corpus_index(index: CorpusIndexArtifact, path: str) -> str:
    with gzip.open(path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_corpus_index(path: str) -> CorpusIndexArtifact:
    with gzip.open(path, "rb") as f:
        return pickle.load(f)
