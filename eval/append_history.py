"""Append the latest eval run to eval/history.json for the Streamlit dashboard.

Can be used two ways:
    * imported:  append_run(df)            # df from harness.run_eval
    * standalone: uv run python eval/append_history.py   # reads last_run.json
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pandas as pd

from harness import (  # type: ignore[import-not-found]
    HISTORY_PATH,
    LAST_RUN_PATH,
    METRIC_NAMES,
    mean_scores,
)


def append_run(df: pd.DataFrame, path: Path = HISTORY_PATH) -> dict:
    """Append one run record (timestamp + means + per-pair) to history.json."""
    means = mean_scores(df)

    # Per-pair faithfulness table for the dashboard's "worst pairs" view.
    per_pair = []
    for i, row in df.iterrows():
        per_pair.append(
            {
                "id": f"row-{i}",
                "question": str(row.get("user_input", ""))[:120],
                "faithfulness": _nan_safe(row.get("faithfulness")),
                "answer_relevancy": _nan_safe(row.get("answer_relevancy")),
                "context_precision": _nan_safe(row.get("context_precision")),
                "context_recall": _nan_safe(row.get("context_recall")),
            }
        )

    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "metrics": means,
        "per_pair": per_pair,
    }

    history = json.loads(path.read_text()) if path.exists() else []
    history.append(entry)
    path.write_text(json.dumps(history, indent=2))
    return entry


def _nan_safe(value) -> float | None:
    """Convert NaN to None so the JSON is clean for the dashboard."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN != NaN


def main() -> None:
    df = pd.read_json(str(LAST_RUN_PATH))
    entry = append_run(df)
    print("Appended run at", entry["timestamp"])
    for name in METRIC_NAMES:
        if name in entry["metrics"]:
            print(f"  {name:<20} {entry['metrics'][name]:.4f}")


if __name__ == "__main__":
    main()
