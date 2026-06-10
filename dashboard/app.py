"""Streamlit regression dashboard for the RAG eval harness.

Run it with:
    uv run streamlit run dashboard/app.py
Then open http://localhost:8501

It reads eval/history.json (one record per eval run) and shows:
    1. A line chart of each Ragas metric over time.
    2. Pass/fail status of the latest run against each threshold.
    3. A table of the 10 worst pairs (by faithfulness) in the latest run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the shared thresholds importable so the dashboard and pytest agree.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from thresholds import THRESHOLDS  # type: ignore[import-not-found]  # noqa: E402

HISTORY_PATH = ROOT / "eval" / "history.json"

st.set_page_config(page_title="RAG Eval Dashboard", layout="wide")  # wide layout
st.title("RAG Evaluation Regression Dashboard")  # page heading


@st.cache_data  # cache so a page reload is instant unless the file changed
def load_history(path: str) -> list[dict]:
    # Load the list of historical eval runs from disk.
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text())


history = load_history(str(HISTORY_PATH))  # list of run records
if not history:  # guard: nothing to show yet
    st.warning(
        "No eval runs found in eval/history.json. "
        "Run `uv run python eval/run_ragas.py` first."
    )
    st.stop()  # halt rendering gracefully


# ── 1. Metric trend over time ───────────────────────────────────────────────
st.header("Metric trend over time")  # section header
# One row per run, columns = the four metrics, index = timestamp.
trend = pd.DataFrame(
    [{"timestamp": run["timestamp"], **run["metrics"]} for run in history]
).set_index("timestamp")  # x-axis = run time
st.line_chart(trend)  # one auto-legended line per metric


# ── 2. Latest run: threshold status ─────────────────────────────────────────
st.header("Latest run: threshold status")  # section header
latest = history[-1]["metrics"]  # most recent run's mean scores
cols = st.columns(len(THRESHOLDS))  # one column per metric
for col, (metric, thresh) in zip(cols, THRESHOLDS.items()):
    score = latest.get(metric)  # this run's score (may be None)
    if score is None:  # metric missing — show neutral state
        col.metric(label=metric, value="n/a")
        col.info("no data")
        continue
    passed = score >= thresh  # boolean gate
    col.metric(
        label=metric,
        value=f"{score:.3f}",
        delta=f"{score - thresh:+.3f} vs thr",  # gap to the threshold
    )
    # Color-coded verdict under each metric.
    (col.success if passed else col.error)("PASS" if passed else "FAIL")


# ── 3. 10 worst pairs by faithfulness (latest run) ──────────────────────────
st.header("10 worst pairs (latest run, by faithfulness)")  # section header
per_pair = pd.DataFrame(history[-1]["per_pair"])  # per-pair scores of latest run
if per_pair.empty:
    st.info("No per-pair data in the latest run.")
else:
    # Sort ascending by faithfulness so the worst offenders are on top.
    worst = per_pair.sort_values("faithfulness", na_position="first").head(10)
    st.dataframe(
        worst[["id", "question", "faithfulness", "context_recall"]],
        use_container_width=True,
    )
