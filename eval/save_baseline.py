"""Promote the latest eval run to the regression baseline.

Run this ONLY after a run you have reviewed and are happy with:
    uv run python eval/save_baseline.py

The regression test (tests/test_regression.py) compares future runs against
eval/baseline.json and fails if any metric drops more than the allowed amount.
"""
from __future__ import annotations

import json

import pandas as pd

from harness import (  # type: ignore[import-not-found]
    BASELINE_PATH,
    LAST_RUN_PATH,
    mean_scores,
)


def main() -> None:
    df = pd.read_json(str(LAST_RUN_PATH))
    baseline = mean_scores(df)
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2))
    print("Baseline updated:")
    for name, score in baseline.items():
        print(f"  {name:<20} {score:.4f}")


if __name__ == "__main__":
    main()
