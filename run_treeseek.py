import argparse
import os
import json
import copy
from treeseek import (
    build_pdf_tree_from_opt,
    build_query_index,
    build_corpus_from_directory,
    load_query_index,
    load_corpus_index,
    rerank_query_results,
    save_query_index,
    search_index,
    search_corpus,
)
from treeseek.corpus.corpus_models import CorpusQueryRequest
from treeseek.markdown_tree import (
    build_markdown_tree,
    extract_node_text_content,
    extract_nodes_from_markdown,
)
from treeseek.word_tree import build_word_tree, enrich_structure_with_docx_text
from treeseek.utils import ConfigLoader, add_node_text, get_page_tokens


def is_yes(value):
    return str(value).strip().lower() == "yes"


def has_structure_text(data):
    if isinstance(data, dict):
        if data.get("text"):
            return True
        if data.get("nodes"):
            return has_structure_text(data["nodes"])
        return False
    if isinstance(data, list):
        return any(has_structure_text(item) for item in data)
    return False


def enrich_pdf_structure_with_text(result, pdf_path, model=None):
    enriched = copy.deepcopy(result)
    page_list = get_page_tokens(pdf_path, model=model)
    add_node_text(enriched["structure"], page_list)
    return enriched


def enrich_markdown_structure_with_text(result, md_path):
    enriched = copy.deepcopy(result)
    with open(md_path, "r", encoding="utf-8") as f:
        markdown_content = f.read()

    node_list, markdown_lines = extract_nodes_from_markdown(markdown_content)
    nodes_with_content = extract_node_text_content(node_list, markdown_lines)
    text_by_key = {(item["line_num"], item["title"]): item["text"] for item in nodes_with_content}

    def attach_text(nodes):
        for node in nodes:
            line_num = node.get("line_num")
            title = node.get("title")
            if line_num is not None:
                node["text"] = text_by_key.get((line_num, title), node.get("text"))
            if node.get("nodes"):
                attach_text(node["nodes"])

    attach_text(enriched["structure"])
    return enriched


def enrich_word_structure_with_text(result, docx_path):
    enriched = copy.deepcopy(result)
    enrich_structure_with_docx_text(enriched["structure"], docx_path)
    return enriched


def build_indexable_result(result, args, opt):
    include_text = is_yes(args.include_text or opt.index_include_text)
    if not include_text or has_structure_text(result.get("structure", [])):
        return result, include_text

    if args.pdf_path:
        return enrich_pdf_structure_with_text(result, args.pdf_path, model=opt.model), include_text
    if args.docx_path:
        return enrich_word_structure_with_text(result, args.docx_path), include_text
    return enrich_markdown_structure_with_text(result, args.md_path), include_text


def build_field_weights(opt):
    return {
        "title": opt.weight_title,
        "path_titles": opt.weight_path,
        "summary": opt.weight_summary,
        "prefix_summary": opt.weight_prefix_summary,
        "text": opt.weight_text,
    }


def build_bonuses(opt):
    return {
        "exact_title": opt.bonus_exact_title,
        "phrase": opt.bonus_phrase,
        "leaf": opt.bonus_leaf,
        "all_terms_hit": opt.bonus_all_terms_hit,
        "proximity": opt.bonus_proximity,
    }


def emit_query_results(doc_name, query, index_path, results):
    print(json.dumps({
        "doc_name": doc_name,
        "query": query,
        "index_path": index_path,
        "results": [item.to_dict() for item in results],
    }, indent=2, ensure_ascii=False))


def emit_corpus_query_results(corpus_name, query, corpus_index_path, results):
    print(json.dumps({
        "corpus_name": corpus_name,
        "query": query,
        "corpus_index_path": corpus_index_path,
        "results": [item.to_dict() for item in results],
    }, indent=2, ensure_ascii=False))


def execute_query(index, args, opt, index_path):
    top_k = args.top_k or opt.query_default_top_k
    leaf_only = is_yes(args.leaf_only or opt.query_leaf_only)
    debug_explain = is_yes(args.debug_explain or opt.debug_explain_default)
    results = search_index(
        index,
        args.query,
        top_k=top_k,
        expand_ancestors=opt.query_expand_ancestors,
        leaf_only=leaf_only,
        debug_explain=debug_explain,
    )
    if is_yes(args.rerank_with_llm):
        results = rerank_query_results(
            index,
            args.query,
            results,
            model=opt.model,
            top_k=args.rerank_top_k,
        )
    emit_query_results(index.doc_id, args.query, index_path, results)


def execute_corpus_query(corpus_index, args, opt, corpus_index_path):
    top_k = args.top_k or opt.query_default_top_k
    leaf_only = is_yes(args.leaf_only or opt.query_leaf_only)
    debug_explain = is_yes(args.debug_explain or opt.debug_explain_default)
    tags = [tag.strip() for tag in (args.tags or "").split(",") if tag.strip()]
    request = CorpusQueryRequest(
        query=args.query,
        top_k=top_k,
        doc_id=args.doc_id,
        doc_type=args.doc_type,
        tags=tags,
        source=args.source,
        created_at_from=args.created_at_from,
        created_at_to=args.created_at_to,
        leaf_only=leaf_only,
        rerank_with_llm=is_yes(args.rerank_with_llm),
        debug_explain=debug_explain,
    )
    results = search_corpus(corpus_index, request, model=opt.model)
    emit_corpus_query_results(corpus_index.corpus_name, args.query, corpus_index_path, results)


def run_interactive_loop(run_query, *, initial_state: dict | None = None):
    state = {
        "top_k": 10,
        "leaf_only": "no",
        "rerank_with_llm": "no",
        "debug_explain": "no",
        "doc_id": None,
    }
    if initial_state:
        state.update(initial_state)

    print("Interactive mode started. Use /exit to quit.")
    while True:
        try:
            query = input("treeseek> ").strip()
        except EOFError:
            print()
            break

        if not query:
            continue
        if query == "/exit":
            break
        if query.startswith("/topk "):
            state["top_k"] = int(query.split(" ", 1)[1].strip())
            print(f"top_k={state['top_k']}")
            continue
        if query.startswith("/leaf "):
            state["leaf_only"] = query.split(" ", 1)[1].strip().lower()
            print(f"leaf_only={state['leaf_only']}")
            continue
        if query.startswith("/rerank "):
            state["rerank_with_llm"] = query.split(" ", 1)[1].strip().lower()
            print(f"rerank_with_llm={state['rerank_with_llm']}")
            continue
        if query.startswith("/debug "):
            state["debug_explain"] = query.split(" ", 1)[1].strip().lower()
            print(f"debug_explain={state['debug_explain']}")
            continue
        if query.startswith("/doc "):
            state["doc_id"] = query.split(" ", 1)[1].strip()
            print(f"doc_id={state['doc_id']}")
            continue

        run_query(query, state)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process PDF or Markdown document and generate structure')
    parser.add_argument('--pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument('--md_path', type=str, help='Path to the Markdown file')
    parser.add_argument('--docx_path', '--word_path', dest='docx_path', type=str, help='Path to the Word (.docx/.docm) file')
    parser.add_argument('--index-path', type=str, default=None,
                      help='Path to an existing query index for query-only mode')
    parser.add_argument('--corpus-input-dir', type=str, default=None,
                      help='Path to a directory of documents for corpus build mode')
    parser.add_argument('--corpus-index-path', type=str, default=None,
                      help='Path to an existing corpus index for corpus query mode')
    parser.add_argument('--corpus-name', type=str, default='default',
                      help='Corpus name used for corpus build output')
    parser.add_argument('--corpus-exclude-glob', action='append', default=None,
                      help='Glob pattern to exclude files from corpus build; can be repeated')

    parser.add_argument('--model', type=str, default=None, help='Model to use (overrides config.yaml)')

    parser.add_argument('--toc-check-pages', type=int, default=None,
                      help='Number of pages to check for table of contents (PDF only)')
    parser.add_argument('--max-pages-per-node', type=int, default=None,
                      help='Maximum number of pages per node (PDF only)')
    parser.add_argument('--max-tokens-per-node', type=int, default=None,
                      help='Maximum number of tokens per node (PDF only)')

    parser.add_argument('--if-add-node-id', type=str, default=None,
                      help='Whether to add node id to the node')
    parser.add_argument('--if-add-node-summary', type=str, default=None,
                      help='Whether to add summary to the node')
    parser.add_argument('--if-add-doc-description', type=str, default=None,
                      help='Whether to add doc description to the doc')
    parser.add_argument('--if-add-node-text', type=str, default=None,
                      help='Whether to add text to the node')
    parser.add_argument('--build-query-index', type=str, default='no',
                      help='Whether to build a query index artifact')
    parser.add_argument('--index-output-dir', type=str, default='./results',
                      help='Directory for saving query index artifacts')
    parser.add_argument('--query', type=str, default=None,
                      help='Run a query against the generated or cached query index')
    parser.add_argument('--top-k', type=int, default=None,
                      help='Number of query results to return')
    parser.add_argument('--leaf-only', type=str, default=None,
                      help='Whether to restrict query results to leaf nodes')
    parser.add_argument('--include-text', type=str, default=None,
                      help='Whether to index leaf text when building the query index')
    parser.add_argument('--rerank-with-llm', type=str, default='no',
                      help='Whether to rerank deterministic query results with an LLM')
    parser.add_argument('--rerank-top-k', type=int, default=None,
                      help='Number of top results to send to the LLM reranker')
    parser.add_argument('--debug-explain', type=str, default='no',
                      help='Whether to include detailed explain fields in query results')
    parser.add_argument('--interactive', type=str, default='no',
                      help='Whether to enter interactive query mode')
    parser.add_argument('--doc-id', type=str, default=None,
                      help='Document id filter for corpus query mode')
    parser.add_argument('--doc-type', type=str, default=None,
                      help='Document type filter for corpus query mode')
    parser.add_argument('--tags', type=str, default=None,
                      help='Comma-separated tags filter for corpus query mode')
    parser.add_argument('--source', type=str, default=None,
                      help='Source filter for corpus query mode')
    parser.add_argument('--created-at-from', type=str, default=None,
                      help='Inclusive lower bound ISO timestamp for corpus query mode')
    parser.add_argument('--created-at-to', type=str, default=None,
                      help='Inclusive upper bound ISO timestamp for corpus query mode')
                      
    # Markdown specific arguments
    parser.add_argument('--if-thinning', type=str, default='no',
                      help='Whether to apply tree thinning for markdown (markdown only)')
    parser.add_argument('--thinning-threshold', type=int, default=5000,
                      help='Minimum token threshold for thinning (markdown only)')
    parser.add_argument('--summary-token-threshold', type=int, default=200,
                      help='Token threshold for generating summaries (markdown only)')
    args = parser.parse_args()
    
    selected_sources = [
        bool(args.pdf_path),
        bool(args.md_path),
        bool(args.docx_path),
        bool(args.corpus_input_dir),
        bool(args.corpus_index_path),
    ]
    if sum(selected_sources) > 1:
        raise ValueError("Only one source mode can be specified at a time")

    if not args.pdf_path and not args.md_path and not args.docx_path and not args.index_path and not args.corpus_input_dir and not args.corpus_index_path:
        raise ValueError("Either --pdf_path, --md_path, --docx_path, --index-path, --corpus-input-dir, or --corpus-index-path must be specified")

    if args.index_path and not os.path.isfile(args.index_path):
        raise ValueError(f"Query index file not found: {args.index_path}")
    if args.corpus_index_path and not os.path.isfile(args.corpus_index_path):
        raise ValueError(f"Corpus index file not found: {args.corpus_index_path}")

    if args.index_path and not args.pdf_path and not args.md_path and not args.docx_path:
        if not args.query and not is_yes(args.interactive):
            raise ValueError("--query must be specified when using --index-path")

        user_opt = {
            'model': args.model,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'index_include_text': args.include_text,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        opt = ConfigLoader().load({k: v for k, v in user_opt.items() if v is not None})
        query_index = load_query_index(args.index_path)
        if is_yes(args.interactive):
            def _run(query, state):
                args.query = query
                args.top_k = state["top_k"]
                args.leaf_only = state["leaf_only"]
                args.rerank_with_llm = state["rerank_with_llm"]
                args.debug_explain = state["debug_explain"]
                execute_query(query_index, args, opt, args.index_path)
            run_interactive_loop(_run)
        else:
            execute_query(query_index, args, opt, args.index_path)
        raise SystemExit(0)

    if args.corpus_index_path and not args.pdf_path and not args.md_path and not args.docx_path and not args.corpus_input_dir:
        if not args.query and not is_yes(args.interactive):
            raise ValueError("--query must be specified when using --corpus-index-path")

        user_opt = {
            'model': args.model,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'index_include_text': args.include_text,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        opt = ConfigLoader().load({k: v for k, v in user_opt.items() if v is not None})
        corpus_index = load_corpus_index(args.corpus_index_path)
        if is_yes(args.interactive):
            def _run(query, state):
                args.query = query
                args.top_k = state["top_k"]
                args.leaf_only = state["leaf_only"]
                args.rerank_with_llm = state["rerank_with_llm"]
                args.debug_explain = state["debug_explain"]
                args.doc_id = state.get("doc_id")
                execute_corpus_query(corpus_index, args, opt, args.corpus_index_path)
            run_interactive_loop(_run)
        else:
            execute_corpus_query(corpus_index, args, opt, args.corpus_index_path)
        raise SystemExit(0)

    if args.corpus_input_dir:
        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'index_include_text': args.include_text,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        corpus_index, corpus_index_path = build_corpus_from_directory(
            args.corpus_input_dir,
            corpus_name=args.corpus_name,
            output_dir="./results/corpus",
            user_opt={k: v for k, v in user_opt.items() if v is not None},
            exclude_globs=args.corpus_exclude_glob or [],
        )
        print(json.dumps({
            "corpus_name": corpus_index.corpus_name,
            "corpus_index_path": corpus_index_path,
            "document_count": len(corpus_index.documents),
            "exclude_globs": corpus_index.exclude_globs,
        }, indent=2, ensure_ascii=False))
        raise SystemExit(0)
    
    if args.pdf_path:
        # Validate PDF file
        if not args.pdf_path.lower().endswith('.pdf'):
            raise ValueError("PDF file must have .pdf extension")
        if not os.path.isfile(args.pdf_path):
            raise ValueError(f"PDF file not found: {args.pdf_path}")
            
        # Process PDF file
        user_opt = {
            'model': args.model,
            'toc_check_page_num': args.toc_check_pages,
            'max_page_num_each_node': args.max_pages_per_node,
            'max_token_num_each_node': args.max_tokens_per_node,
            'if_add_node_id': args.if_add_node_id,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'index_include_text': args.include_text,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        opt = ConfigLoader().load({k: v for k, v in user_opt.items() if v is not None})

        # Process the PDF
        result = build_pdf_tree_from_opt(args.pdf_path, opt)
        print('Parsing done, saving to file...')
        
        # Save results
        pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{pdf_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        print(f'Tree structure saved to: {output_file}')

        query_index = None
        query_index_output_dir = args.index_output_dir
        os.makedirs(query_index_output_dir, exist_ok=True)
        query_index_path = os.path.join(query_index_output_dir, f'{pdf_name}_query_index.pkl.gz')
        include_text = is_yes(args.include_text or opt.index_include_text)

        if args.query and os.path.isfile(query_index_path):
            query_index = load_query_index(query_index_path)
            if query_index.include_text != include_text:
                query_index = None

        if query_index is None and (is_yes(args.build_query_index) or args.query):
            indexable_result, include_text = build_indexable_result(result, args, opt)
            query_index = build_query_index(
                indexable_result,
                include_text=include_text,
                postings_backend=opt.index_postings_backend,
                field_weights=build_field_weights(opt),
                bonuses=build_bonuses(opt),
                snippet_max_chars=opt.snippet_max_chars,
                snippet_context_chars=opt.snippet_context_chars,
                debug_explain_default=is_yes(args.debug_explain or opt.debug_explain_default),
                bm25_k1=opt.bm25_k1,
                bm25_b=opt.bm25_b,
                proximity_window=opt.proximity_window,
                diversity_penalty=opt.diversity_penalty,
            )

        if query_index is not None and is_yes(args.build_query_index):
            save_query_index(query_index, query_index_path)
            print(f'Query index saved to: {query_index_path}')

        if args.query and query_index is not None:
            execute_query(
                query_index,
                args,
                opt,
                query_index_path if os.path.isfile(query_index_path) else None,
            )
    elif args.docx_path:
        if not args.docx_path.lower().endswith(('.docx', '.docm')):
            raise ValueError("Word file must have .docx or .docm extension")
        if not os.path.isfile(args.docx_path):
            raise ValueError(f"Word file not found: {args.docx_path}")

        print('Processing Word file...')
        import asyncio
        from treeseek.utils import ConfigLoader
        config_loader = ConfigLoader()

        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'index_include_text': args.include_text,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        opt = config_loader.load({k: v for k, v in user_opt.items() if v is not None})

        result = asyncio.run(
            build_word_tree(
                docx_path=args.docx_path,
                if_thinning=args.if_thinning.lower() == 'yes',
                min_token_threshold=args.thinning_threshold,
                if_add_node_summary=opt.if_add_node_summary,
                summary_token_threshold=args.summary_token_threshold,
                model=opt.model,
                if_add_doc_description=opt.if_add_doc_description,
                if_add_node_text=opt.if_add_node_text,
                if_add_node_id=opt.if_add_node_id,
            )
        )

        print('Parsing done, saving to file...')
        docx_name = os.path.splitext(os.path.basename(args.docx_path))[0]
        output_dir = './results'
        output_file = f'{output_dir}/{docx_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f'Tree structure saved to: {output_file}')

        query_index = None
        query_index_output_dir = args.index_output_dir
        os.makedirs(query_index_output_dir, exist_ok=True)
        query_index_path = os.path.join(query_index_output_dir, f'{docx_name}_query_index.pkl.gz')
        include_text = is_yes(args.include_text or opt.index_include_text)

        if args.query and os.path.isfile(query_index_path):
            query_index = load_query_index(query_index_path)
            if query_index.include_text != include_text:
                query_index = None

        if query_index is None and (is_yes(args.build_query_index) or args.query):
            indexable_result, include_text = build_indexable_result(result, args, opt)
            query_index = build_query_index(
                indexable_result,
                include_text=include_text,
                postings_backend=opt.index_postings_backend,
                field_weights=build_field_weights(opt),
                bonuses=build_bonuses(opt),
                snippet_max_chars=opt.snippet_max_chars,
                snippet_context_chars=opt.snippet_context_chars,
                debug_explain_default=is_yes(args.debug_explain or opt.debug_explain_default),
                bm25_k1=opt.bm25_k1,
                bm25_b=opt.bm25_b,
                proximity_window=opt.proximity_window,
                diversity_penalty=opt.diversity_penalty,
            )

        if query_index is not None and is_yes(args.build_query_index):
            save_query_index(query_index, query_index_path)
            print(f'Query index saved to: {query_index_path}')

        if args.query and query_index is not None:
            execute_query(
                query_index,
                args,
                opt,
                query_index_path if os.path.isfile(query_index_path) else None,
            )
            
    elif args.md_path:
        # Validate Markdown file
        if not args.md_path.lower().endswith(('.md', '.markdown')):
            raise ValueError("Markdown file must have .md or .markdown extension")
        if not os.path.isfile(args.md_path):
            raise ValueError(f"Markdown file not found: {args.md_path}")
            
        # Process markdown file
        print('Processing markdown file...')
        
        # Process the markdown
        import asyncio
        
        # Use ConfigLoader to get consistent defaults (matching PDF behavior)
        from treeseek.utils import ConfigLoader
        config_loader = ConfigLoader()
        
        # Create options dict with user args
        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id,
            'index_backend': 'inverted',
            'index_postings_backend': None,
            'index_include_text': args.include_text,
            'query_default_top_k': args.top_k,
            'query_expand_ancestors': None,
            'query_leaf_only': args.leaf_only,
            'weight_title': None,
            'weight_path': None,
            'weight_summary': None,
            'weight_prefix_summary': None,
            'weight_text': None,
            'bonus_exact_title': None,
            'bonus_phrase': None,
            'bonus_leaf': None,
            'bonus_all_terms_hit': None,
            'bonus_proximity': None,
            'bm25_k1': None,
            'bm25_b': None,
            'proximity_window': None,
            'diversity_penalty': None,
            'debug_explain_default': args.debug_explain,
        }
        
        # Load config with defaults from config.yaml
        opt = config_loader.load({k: v for k, v in user_opt.items() if v is not None})
        
        result = asyncio.run(build_markdown_tree(
            md_path=args.md_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=opt.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id
        ))
        
        print('Parsing done, saving to file...')
        
        # Save results
        md_name = os.path.splitext(os.path.basename(args.md_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{md_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f'Tree structure saved to: {output_file}')

        query_index = None
        query_index_output_dir = args.index_output_dir
        os.makedirs(query_index_output_dir, exist_ok=True)
        query_index_path = os.path.join(query_index_output_dir, f'{md_name}_query_index.pkl.gz')
        include_text = is_yes(args.include_text or opt.index_include_text)

        if args.query and os.path.isfile(query_index_path):
            query_index = load_query_index(query_index_path)
            if query_index.include_text != include_text:
                query_index = None

        if query_index is None and (is_yes(args.build_query_index) or args.query):
            indexable_result, include_text = build_indexable_result(result, args, opt)
            query_index = build_query_index(
                indexable_result,
                include_text=include_text,
                postings_backend=opt.index_postings_backend,
                field_weights=build_field_weights(opt),
                bonuses=build_bonuses(opt),
                snippet_max_chars=opt.snippet_max_chars,
                snippet_context_chars=opt.snippet_context_chars,
                debug_explain_default=is_yes(args.debug_explain or opt.debug_explain_default),
                bm25_k1=opt.bm25_k1,
                bm25_b=opt.bm25_b,
                proximity_window=opt.proximity_window,
                diversity_penalty=opt.diversity_penalty,
            )

        if query_index is not None and is_yes(args.build_query_index):
            save_query_index(query_index, query_index_path)
            print(f'Query index saved to: {query_index_path}')

        if args.query and query_index is not None:
            execute_query(
                query_index,
                args,
                opt,
                query_index_path if os.path.isfile(query_index_path) else None,
            )
