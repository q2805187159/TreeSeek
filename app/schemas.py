from __future__ import annotations

from pydantic import BaseModel, Field


class BuildIndexRequest(BaseModel):
    path: str
    doc_type: str = Field(pattern="^(pdf|markdown|word)$")
    include_text: bool = False
    index_output_dir: str = "./results"


class BuildCorpusRequest(BaseModel):
    input_dir: str
    corpus_name: str = "default"
    exclude_globs: list[str] = []


class QueryRequestModel(BaseModel):
    index_path: str
    query: str
    top_k: int = 10
    leaf_only: bool = False
    debug_explain: bool = False
    rerank_with_llm: bool = False


class CorpusQueryRequestModel(BaseModel):
    corpus_index_path: str
    query: str
    top_k: int = 10
    doc_id: str | None = None
    doc_type: str | None = None
    tags: list[str] = []
    source: str | None = None
    created_at_from: str | None = None
    created_at_to: str | None = None
    leaf_only: bool = False
    debug_explain: bool = False
    rerank_with_llm: bool = False


class RerankRequestModel(BaseModel):
    index_path: str
    query: str
    top_k: int = 5
