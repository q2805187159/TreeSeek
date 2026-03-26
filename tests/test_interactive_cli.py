from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_interactive_query_only_mode(local_tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    md_path = local_tmp_path / "sample.md"
    index_dir = local_tmp_path / "index"
    index_path = index_dir / "sample_query_index.pkl.gz"

    md_path.write_text(
        "# Root\n\n## Retrieval Design\n\nRetrieval design guidance.\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(repo_root / "run_treeseek.py"),
            "--md_path",
            str(md_path),
            "--if-add-node-summary",
            "no",
            "--build-query-index",
            "yes",
            "--include-text",
            "yes",
            "--index-output-dir",
            str(index_dir),
        ],
        cwd=local_tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "run_treeseek.py"),
            "--index-path",
            str(index_path),
            "--interactive",
            "yes",
        ],
        cwd=local_tmp_path,
        input="retrieval design\n/topk 3\n/debug yes\n/exit\n",
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=True,
    )

    assert "Interactive mode started" in completed.stdout
    assert "Retrieval Design" in completed.stdout
    assert "top_k=3" in completed.stdout
    assert "debug_explain=yes" in completed.stdout
