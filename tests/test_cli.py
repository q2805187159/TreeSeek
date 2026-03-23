from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_markdown_cli_builds_query_index_and_runs_query(local_tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    md_path = local_tmp_path / "sample.md"
    index_dir = local_tmp_path / "index"
    results_dir = local_tmp_path / "results"

    md_path.write_text(
        "# Root\n\n"
        "Overview text.\n\n"
        "## Direct-to-Consumer\n\n"
        "Direct-to-consumer subscriber growth improved in Q1.\n\n"
        "## Parks\n\n"
        "Theme park attendance remained resilient.\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(repo_root / "run_rag.py"),
        "--md_path",
        str(md_path),
        "--if-add-node-summary",
        "no",
        "--build-query-index",
        "yes",
        "--query",
        "direct-to-consumer",
        "--top-k",
        "2",
        "--include-text",
        "yes",
        "--index-output-dir",
        str(index_dir),
    ]

    completed = subprocess.run(
        command,
        cwd=local_tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=True,
    )

    assert (results_dir / "sample_structure.json").exists()
    assert (index_dir / "sample_query_index.pkl.gz").exists()
    assert '"query": "direct-to-consumer"' in completed.stdout
    assert "Direct-to-Consumer" in completed.stdout


def test_query_only_mode_uses_existing_index_without_source_document(local_tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    md_path = local_tmp_path / "sample.md"
    index_dir = local_tmp_path / "index"
    index_path = index_dir / "sample_query_index.pkl.gz"

    md_path.write_text(
        "# Root\n\n"
        "Overview text.\n\n"
        "## Direct-to-Consumer\n\n"
        "Direct-to-consumer subscriber growth improved in Q1.\n\n",
        encoding="utf-8",
    )

    build_command = [
        sys.executable,
        str(repo_root / "run_rag.py"),
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
    ]
    subprocess.run(
        build_command,
        cwd=local_tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=True,
    )

    md_path.unlink()

    query_command = [
        sys.executable,
        str(repo_root / "run_rag.py"),
        "--index-path",
        str(index_path),
        "--query",
        "direct-to-consumer",
        "--top-k",
        "2",
    ]
    completed = subprocess.run(
        query_command,
        cwd=local_tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=True,
    )

    assert index_path.exists()
    assert '"query": "direct-to-consumer"' in completed.stdout
    assert "Direct-to-Consumer" in completed.stdout
