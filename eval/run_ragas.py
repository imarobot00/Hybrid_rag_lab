"""Run the golden eval set through RAG + Ragas, save results, append history.

This is a thin CLI wrapper around the shared harness so the scoring logic
lives in exactly ONE place (eval/harness.py).

Usage (make sure the FastAPI server is running first):
    uv run python eval/run_ragas.py

What it does:
    1. Loads the golden Q&A pairs (full set, or EVAL_SUBSET=N for a quick run).
    2. Runs each question through POST /query and scores with Ragas.
       Strict mode: if the server is down or returns no contexts, it RAISES
       loudly instead of producing the null/garbage scores we saw before.
    3. Saves per-row results to eval/last_run.json.
    4. Appends the run's mean scores to eval/history.json (for the dashboard).
"""
from __future__ import annotations

import sys

from append_history import append_run  # type: ignore[import-not-found]
from harness import (  # type: ignore[import-not-found]
    GROQ_API_KEY,
    LAST_RUN_PATH,
    METRIC_NAMES,
    load_golden,
    mean_scores,
    run_eval,
)


def main() -> None:
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("RAG EVALUATION - Week 4")
    print("=" * 60)

    golden = load_golden()
    print(f"\nLoaded {len(golden)} golden eval pairs")

    # Strict: fail loudly if the server is down or returns empty contexts.
    df = run_eval(golden, strict=True)

    # Save the full per-row table for inspection / the dashboard.
    df.to_json(str(LAST_RUN_PATH), orient="records", indent=2)
    print(f"\nPer-row results saved to {LAST_RUN_PATH}")

    # Print the headline mean scores.
    means = mean_scores(df)
    print("\n" + "=" * 60)
    print("MEAN SCORES")
    print("=" * 60)
    for name in METRIC_NAMES:
        if name in means:
            print(f"  {name:<20} {means[name]:.3f}")

    # Append to the rolling history used by the Streamlit dashboard.
    append_run(df)
    print("\nAppended this run to eval/history.json")


if __name__ == "__main__":
    main()
