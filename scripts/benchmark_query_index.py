import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from treeseek import build_query_index, load_query_index, rerank_query_results, save_query_index, search_index


def main():
    parser = argparse.ArgumentParser(description="Benchmark TreeSeek query index build/load/search flow")
    parser.add_argument("--structure-path", required=True, help="Path to a *_structure.json file")
    parser.add_argument("--query", action="append", required=True, help="Query to execute; can be passed multiple times")
    parser.add_argument("--index-path", default=None, help="Optional output path for the serialized query index")
    parser.add_argument("--include-text", default="no", help="Whether to include text indexing if present in the structure")
    parser.add_argument("--rerank-with-llm", default="no", help="Whether to measure LLM rerank on top of deterministic results")
    parser.add_argument("--rerank-top-k", type=int, default=3, help="Number of deterministic results to rerank")
    args = parser.parse_args()

    with open(args.structure_path, "r", encoding="utf-8") as f:
        document = json.load(f)

    include_text = str(args.include_text).strip().lower() == "yes"
    rerank = str(args.rerank_with_llm).strip().lower() == "yes"
    index_path = args.index_path or args.structure_path.replace("_structure.json", "_query_index.pkl.gz")

    start = time.perf_counter()
    index = build_query_index(document, include_text=include_text)
    build_seconds = time.perf_counter() - start

    start = time.perf_counter()
    save_query_index(index, index_path)
    saved_seconds = time.perf_counter() - start

    start = time.perf_counter()
    loaded_index = load_query_index(index_path)
    load_seconds = time.perf_counter() - start

    query_stats = []
    for query in args.query:
        start = time.perf_counter()
        results = search_index(loaded_index, query, top_k=10)
        search_seconds = time.perf_counter() - start

        rerank_seconds = None
        if rerank and results:
            start = time.perf_counter()
            rerank_query_results(loaded_index, query, results, top_k=args.rerank_top_k)
            rerank_seconds = time.perf_counter() - start

        query_stats.append(
            {
                "query": query,
                "result_count": len(results),
                "search_seconds": round(search_seconds, 6),
                "rerank_seconds": round(rerank_seconds, 6) if rerank_seconds is not None else None,
            }
        )

    print(json.dumps(
        {
            "structure_path": args.structure_path,
            "index_path": index_path,
            "include_text": include_text,
            "build_seconds": round(build_seconds, 6),
            "save_seconds": round(saved_seconds, 6),
            "load_seconds": round(load_seconds, 6),
            "queries": query_stats,
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
