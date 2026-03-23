from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "tests" / "results"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def load_result_doc(name: str):
    with open(RESULTS_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def annual_report_doc():
    return load_result_doc("2023-annual-report_structure.json")


@pytest.fixture
def earnings_doc():
    return load_result_doc("q1-fy25-earnings_structure.json")


@pytest.fixture
def query_cases():
    with open(FIXTURES_DIR / "query_cases.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def synthetic_text_doc():
    return {
        "doc_name": "synthetic",
        "structure": [
            {
                "title": "Root Overview",
                "start_index": 1,
                "end_index": 3,
                "node_id": "1000",
                "summary": "Root node for synthetic tests.",
                "nodes": [
                    {
                        "title": "Direct-to-Consumer",
                        "start_index": 1,
                        "end_index": 1,
                        "node_id": "1001",
                        "summary": "Streaming revenue and subscriber additions.",
                        "text": "Direct-to-consumer subscriber growth improved in Q1.",
                    },
                    {
                        "title": "Parks",
                        "start_index": 2,
                        "end_index": 2,
                        "node_id": "1002",
                        "summary": "Theme parks and experiences.",
                        "text": "Theme park attendance remained resilient.",
                    },
                ],
            }
        ],
    }


@pytest.fixture
def local_tmp_path():
    base_dir = REPO_ROOT / ".tmp_pytest"
    base_dir.mkdir(exist_ok=True)
    path = base_dir / f"run_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
