from __future__ import annotations

from fastapi import FastAPI

from .schemas import (
    BuildCorpusRequest,
    BuildIndexRequest,
    CorpusQueryRequestModel,
    QueryRequestModel,
    RerankRequestModel,
)
from .services.corpus_service import build_corpus, query_corpus
from .services.query_service import build_single_index, query_single_index, rerank_existing_results

app = FastAPI(title="TreeSeek API", version="0.3.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build-index")
def build_index(request: BuildIndexRequest):
    return build_single_index(
        request.path,
        request.doc_type,
        include_text=request.include_text,
        index_output_dir=request.index_output_dir,
    )


@app.post("/build-corpus")
def build_corpus_endpoint(request: BuildCorpusRequest):
    return build_corpus(request.input_dir, request.corpus_name, request.exclude_globs)


@app.post("/query")
def query_endpoint(request: QueryRequestModel):
    return query_single_index(
        request.index_path,
        request.query,
        top_k=request.top_k,
        leaf_only=request.leaf_only,
        debug_explain=request.debug_explain,
        rerank_with_llm=request.rerank_with_llm,
    )


@app.post("/query-corpus")
def query_corpus_endpoint(request: CorpusQueryRequestModel):
    return query_corpus(
        request.corpus_index_path,
        request.query,
        top_k=request.top_k,
        doc_id=request.doc_id,
        doc_type=request.doc_type,
        tags=request.tags,
        source=request.source,
        created_at_from=request.created_at_from,
        created_at_to=request.created_at_to,
        leaf_only=request.leaf_only,
        debug_explain=request.debug_explain,
        rerank_with_llm=request.rerank_with_llm,
    )


@app.post("/rerank")
def rerank_endpoint(request: RerankRequestModel):
    return rerank_existing_results(request.index_path, request.query, top_k=request.top_k)
