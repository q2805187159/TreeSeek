from __future__ import annotations

import asyncio
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from .corpus_models import CorpusDocumentRecord, CorpusIndexArtifact
from .corpus_storage import save_corpus_index
from .. import build_pdf_tree_from_opt, build_query_index, save_query_index
from ..markdown_tree import build_markdown_tree
from ..utils import ConfigLoader, add_node_text, sanitize_filename
from ..word_tree import build_word_tree, enrich_structure_with_docx_text

SUPPORTED_PATTERNS = {
    "pdf": ("*.pdf",),
    "markdown": ("*.md", "*.markdown"),
    "word": ("*.docx", "*.docm"),
}


def _infer_doc_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".docx", ".docm"}:
        return "word"
    return None


def _generate_doc_id(stem: str, counts: Counter[str]) -> str:
    base = sanitize_filename(stem.lower().replace(" ", "-"))
    counts[base] += 1
    if counts[base] == 1:
        return base
    return f"{base}-{counts[base]}"


def _build_pdf_tree_fallback(path: Path):
    import pymupdf

    doc = pymupdf.open(str(path))
    page_texts = [page.get_text() for page in doc]
    doc.close()
    full_text = "\n".join(text for text in page_texts if text)
    return {
        "doc_name": path.name,
        "structure": [
            {
                "title": path.stem,
                "node_id": "0000",
                "start_index": 1,
                "end_index": max(len(page_texts), 1),
                "text": full_text,
                "summary": full_text[:400] if full_text else path.stem,
            }
        ],
    }


def _build_single_document(path: Path, opt, include_text: bool):
    doc_type = _infer_doc_type(path)
    if doc_type == "pdf":
        try:
            pdf_opt = opt
            if opt.model is None:
                pdf_opt = ConfigLoader().load({**vars(opt), "model": "openai/gpt-4o-mini"})
            result = build_pdf_tree_from_opt(str(path), pdf_opt)
            if include_text:
                import pymupdf

                doc = pymupdf.open(str(path))
                pages = [(page.get_text(), max(1, len(page.get_text().split()))) for page in doc]
                doc.close()
                add_node_text(result["structure"], pages)
        except Exception:
            result = _build_pdf_tree_fallback(path)
        return result
    if doc_type == "markdown":
        result = asyncio.run(
            build_markdown_tree(
                md_path=str(path),
                if_thinning=False,
                min_token_threshold=5000,
                if_add_node_summary=opt.if_add_node_summary,
                summary_token_threshold=200,
                model=opt.model,
                if_add_doc_description=opt.if_add_doc_description,
                if_add_node_text=opt.if_add_node_text,
                if_add_node_id=opt.if_add_node_id,
            )
        )
        return result
    if doc_type == "word":
        result = asyncio.run(
            build_word_tree(
                docx_path=str(path),
                if_thinning=False,
                min_token_threshold=5000,
                if_add_node_summary=opt.if_add_node_summary,
                summary_token_threshold=200,
                model=opt.model,
                if_add_doc_description=opt.if_add_doc_description,
                if_add_node_text=opt.if_add_node_text,
                if_add_node_id=opt.if_add_node_id,
            )
        )
        if include_text:
            enrich_structure_with_docx_text(result["structure"], str(path))
        return result
    raise ValueError(f"Unsupported document type: {path}")


def build_corpus_from_directory(
    input_dir: str,
    *,
    corpus_name: str,
    output_dir: str,
    user_opt: dict | None = None,
    exclude_globs: list[str] | None = None,
):
    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise ValueError(f"Input directory not found: {input_dir}")

    opt = ConfigLoader().load(user_opt or {})
    include_text = str(opt.index_include_text).strip().lower() == "yes"

    corpus_dir = Path(output_dir) / corpus_name
    corpus_dir.mkdir(parents=True, exist_ok=True)
    exclude_patterns = [pattern for pattern in (exclude_globs or []) if pattern]

    files = sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file()
        and _infer_doc_type(path) is not None
        and not any(path.match(pattern) or path.name == pattern for pattern in exclude_patterns)
    )
    counts: Counter[str] = Counter()
    records: list[CorpusDocumentRecord] = []

    for path in files:
        doc_type = _infer_doc_type(path)
        doc_id = _generate_doc_id(path.stem, counts)
        result = _build_single_document(path, opt, include_text)

        structure_path = corpus_dir / f"{doc_id}_structure.json"
        index_path = corpus_dir / f"{doc_id}_query_index.pkl.gz"

        import json

        with open(structure_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        query_index = build_query_index(
            result,
            include_text=include_text,
            postings_backend=opt.index_postings_backend,
            field_weights={
                "title": opt.weight_title,
                "path_titles": opt.weight_path,
                "summary": opt.weight_summary,
                "prefix_summary": opt.weight_prefix_summary,
                "text": opt.weight_text,
            },
            bonuses={
                "exact_title": opt.bonus_exact_title,
                "phrase": opt.bonus_phrase,
                "leaf": opt.bonus_leaf,
                "all_terms_hit": opt.bonus_all_terms_hit,
                "proximity": opt.bonus_proximity,
            },
            snippet_max_chars=opt.snippet_max_chars,
            snippet_context_chars=opt.snippet_context_chars,
            debug_explain_default=str(opt.debug_explain_default).strip().lower() == "yes",
            bm25_k1=opt.bm25_k1,
            bm25_b=opt.bm25_b,
            proximity_window=opt.proximity_window,
            diversity_penalty=opt.diversity_penalty,
        )
        save_query_index(query_index, str(index_path))

        stat = path.stat()
        record = CorpusDocumentRecord(
            doc_id=doc_id,
            doc_name=path.name,
            source_path=str(path),
            doc_type=doc_type,
            tags=[],
            source=input_path.name,
            created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            query_index_path=str(index_path),
        )
        records.append(record)

    doc_id_to_record = {record.doc_id: record for record in records}
    doc_id_to_index_path = {record.doc_id: record.query_index_path for record in records}
    metadata_catalog = {
        "doc_types": sorted({record.doc_type for record in records}),
        "sources": sorted({record.source for record in records}),
        "document_count": len(records),
    }

    corpus_index = CorpusIndexArtifact(
        corpus_name=corpus_name,
        documents=records,
        doc_id_to_record=doc_id_to_record,
        doc_id_to_index_path=doc_id_to_index_path,
        metadata_catalog=metadata_catalog,
        exclude_globs=list(exclude_patterns),
    )
    corpus_index_path = corpus_dir / "corpus_index.pkl.gz"
    save_corpus_index(corpus_index, str(corpus_index_path))
    return corpus_index, str(corpus_index_path)
