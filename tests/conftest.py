"""Pytest fixtures for the RAG evaluation suite.

The expensive work — running all golden questions through the RAG pipeline and
scoring them with Ragas — happens exactly ONCE per test session (scope="session")
and is shared by every test. Without this, each test file would re-run the whole
evaluation and the suite would be unusably slow + expensive.

Prerequisite: the FastAPI server must be running:
    uv run uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

# Make eval/ importable so we can reuse the single-source-of-truth harness.
EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL_DIR))

from harness import (  # type: ignore[import-not-found]  # noqa: E402
    RAG_URL,
    load_golden,
    mean_scores,
    run_eval,
)


def _server_is_up() -> bool:
    """Quick health check so we can fail with a helpful message if it's down."""
    health_url = RAG_URL.rsplit("/", 1)[0] + "/health"
    try:
        return requests.get(health_url, timeout=5).status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def golden() -> list[dict]:
    """The golden eval pairs (optionally subset via EVAL_SUBSET env var)."""
    return load_golden()


@pytest.fixture(scope="session")
def scores(golden) -> dict[str, float]:
    """Run the full eval ONCE and return mean scores for the four metrics.

    Every metric/regression test depends on this fixture, so Ragas runs a
    single time for the whole suite.
    """
    if not _server_is_up():
        pytest.fail(
            f"RAG server not reachable at {RAG_URL}. Start it first:\n"
            f"    uv run uvicorn app.main:app --port 8000",
            pytrace=False,
        )
    df = run_eval(golden, strict=True)  # raises loudly on any RAG error
    return mean_scores(df)
