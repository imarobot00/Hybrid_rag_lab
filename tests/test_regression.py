"""Regression test — fail if any metric dropped more than the allowed amount.

Compares the current run's mean scores against eval/baseline.json (the last
run you reviewed and promoted with `uv run python eval/save_baseline.py`).

If no baseline exists yet, the test is skipped with a clear message rather than
failing — you can't regress against nothing.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from harness import BASELINE_PATH  # type: ignore[import-not-found]  # noqa: E402
from thresholds import MAX_REGRESSION_DROP  # type: ignore[import-not-found]  # noqa: E402


def test_no_metric_regressed(scores):
    if not BASELINE_PATH.exists():
        pytest.skip(
            "No baseline yet. Create one with: "
            "uv run python eval/save_baseline.py"
        )

    baseline = json.loads(BASELINE_PATH.read_text())
    failures = []
    for metric, current in scores.items():
        prev = baseline.get(metric)
        if prev is None:
            continue  # new metric — nothing to compare against
        if current < prev - MAX_REGRESSION_DROP:
            failures.append(
                f"{metric}: {current:.3f} < baseline {prev:.3f} "
                f"- {MAX_REGRESSION_DROP} tolerance"
            )

    assert not failures, "Regression(s) detected:\n" + "\n".join(failures)
