from __future__ import annotations

import os
import re

from .markdown_tree import (
    build_tree_from_nodes,
    generate_summaries_for_structure_md,
    tree_thinning_for_index,
    update_node_list_with_text_token_count,
)
from .utils import (
    create_clean_structure_for_description,
    format_structure,
    generate_doc_description,
    write_node_id,
)


HEADING_STYLE_PATTERNS = [
    re.compile(r"^heading\s+([1-9])$", re.IGNORECASE),
    re.compile(r"^标题\s*([1-9])$"),
]


def _load_docx_document(docx_path: str):
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise ImportError("python-docx is required for Word (.docx/.docm) support") from exc
    return Document(docx_path)


def get_docx_paragraphs(docx_path: str):
    document = _load_docx_document(docx_path)
    paragraphs = []
    for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
        text = (paragraph.text or "").strip()
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style else ""
        paragraphs.append(
            {
                "paragraph_index": paragraph_index,
                "text": text,
                "style_name": style_name or "",
            }
        )
    return paragraphs


def _style_to_heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    normalized = str(style_name).strip()
    for pattern in HEADING_STYLE_PATTERNS:
        match = pattern.match(normalized)
        if match:
            return int(match.group(1))
    if normalized.lower() == "title":
        # Treat document title as a synthetic root above Heading 1 sections so it
        # does not behave like a normal leaf result in leaf-only retrieval.
        return 0
    return None


def extract_nodes_from_docx(docx_path: str):
    paragraphs = get_docx_paragraphs(docx_path)
    node_list = []
    for paragraph in paragraphs:
        level = _style_to_heading_level(paragraph["style_name"])
        if level is None:
            continue
        node_list.append(
            {
                "node_title": paragraph["text"],
                "line_num": paragraph["paragraph_index"],
                "level": level,
            }
        )
    return node_list, paragraphs


def extract_node_text_content_from_docx(node_list, paragraphs, doc_name: str):
    if not paragraphs:
        return [{"title": doc_name, "line_num": 1, "level": 1, "text": ""}]

    if not node_list:
        full_text = "\n".join(item["text"] for item in paragraphs).strip()
        return [{"title": doc_name, "line_num": 1, "level": 1, "text": full_text}]

    all_nodes = []
    for node in node_list:
        all_nodes.append(
            {
                "title": node["node_title"],
                "line_num": node["line_num"],
                "level": node["level"],
            }
        )

    def collect_text_between(start_line: int, end_line: int | None):
        selected = []
        for paragraph in paragraphs:
            paragraph_index = paragraph["paragraph_index"]
            if paragraph_index < start_line:
                continue
            if end_line is not None and paragraph_index >= end_line:
                break
            selected.append(paragraph["text"])
        return "\n".join(selected).strip()

    for idx, node in enumerate(all_nodes):
        end_line = all_nodes[idx + 1]["line_num"] if idx + 1 < len(all_nodes) else None
        node["text"] = collect_text_between(node["line_num"], end_line)

    return all_nodes


def _flatten_word_structure(structure):
    items = []

    def walk(nodes):
        for node in nodes:
            items.append(node)
            if node.get("nodes"):
                walk(node["nodes"])

    walk(structure)
    return items


def enrich_structure_with_docx_text(structure, docx_path: str):
    paragraphs = get_docx_paragraphs(docx_path)
    doc_name = os.path.splitext(os.path.basename(docx_path))[0]
    flat_nodes = _flatten_word_structure(structure)
    nodes = extract_node_text_content_from_docx(
        [
            {
                "node_title": item.get("title"),
                "line_num": item.get("line_num"),
                "level": item.get("level", 1),
            }
            for item in flat_nodes
        ],
        paragraphs,
        doc_name,
    )
    text_by_key = {(item["line_num"], item["title"]): item["text"] for item in nodes}

    def attach(nodes_list):
        for node in nodes_list:
            line_num = node.get("line_num")
            title = node.get("title")
            if line_num is not None:
                node["text"] = text_by_key.get((line_num, title), node.get("text"))
            if node.get("nodes"):
                attach(node["nodes"])

    attach(structure)
    return structure


async def build_word_tree(
    docx_path,
    if_thinning=False,
    min_token_threshold=None,
    if_add_node_summary="no",
    summary_token_threshold=None,
    model=None,
    if_add_doc_description="no",
    if_add_node_text="no",
    if_add_node_id="yes",
):
    doc_name = os.path.splitext(os.path.basename(docx_path))[0]
    node_list, paragraphs = extract_nodes_from_docx(docx_path)
    nodes_with_content = extract_node_text_content_from_docx(node_list, paragraphs, doc_name)

    if if_thinning:
        nodes_with_content = update_node_list_with_text_token_count(nodes_with_content, model=model)
        nodes_with_content = tree_thinning_for_index(nodes_with_content, min_token_threshold, model=model)

    tree_structure = build_tree_from_nodes(nodes_with_content)

    if if_add_node_id == "yes":
        write_node_id(tree_structure)

    if if_add_node_summary == "yes":
        tree_structure = format_structure(
            tree_structure,
            order=["title", "node_id", "summary", "prefix_summary", "text", "line_num", "nodes"],
        )
        tree_structure = await generate_summaries_for_structure_md(
            tree_structure,
            summary_token_threshold=summary_token_threshold,
            model=model,
        )
        if if_add_node_text == "no":
            tree_structure = format_structure(
                tree_structure,
                order=["title", "node_id", "summary", "prefix_summary", "line_num", "nodes"],
            )
        if if_add_doc_description == "yes":
            clean_structure = create_clean_structure_for_description(tree_structure)
            doc_description = generate_doc_description(clean_structure, model=model)
            return {
                "doc_name": os.path.basename(docx_path),
                "doc_description": doc_description,
                "structure": tree_structure,
            }
    else:
        if if_add_node_text == "yes":
            tree_structure = format_structure(
                tree_structure,
                order=["title", "node_id", "summary", "prefix_summary", "text", "line_num", "nodes"],
            )
        else:
            tree_structure = format_structure(
                tree_structure,
                order=["title", "node_id", "summary", "prefix_summary", "line_num", "nodes"],
            )

    return {
        "doc_name": os.path.basename(docx_path),
        "structure": tree_structure,
    }
