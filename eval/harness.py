"""Shared evaluation harness — the single source of truth for Week-4 eval.

Both `eval/run_ragas.py` (CLI) and `tests/conftest.py` (pytest) import from
here so the scoring logic exists in exactly one place.

Key design decisions that fix the "garbage scores" problem:
    * If the RAG endpoint errors, we RAISE by default instead of silently
      appending an "ERROR:" string with empty contexts. Empty contexts are
      what produced the null / 0.0 garbage in the old runs.
    * Metric column names are normalised to a stable set:
      faithfulness, answer_relevancy, context_precision, context_recall.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import requests
from datasets import Dataset
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithoutReference,
    LLMContextRecall,
    ResponseRelevancy,
)

load_dotenv()

# ── Paths ───────────────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden_set.json"
LAST_RUN_PATH = EVAL_DIR / "last_run.json"
BASELINE_PATH = EVAL_DIR / "baseline.json"
HISTORY_PATH = EVAL_DIR / "history.json"

# ── Config (env-overridable so CI can run a cheap subset) ───────────────────
RAG_URL = os.getenv("RAG_URL", "http://localhost:8000/query")
# Use Groq's OpenAI-compatible endpoint as the (free) judge.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "llama-3.1-8b-instant")
# Local embeddings for ResponseRelevancy — must match the index-time model.
JUDGE_EMBED_MODEL = os.getenv("JUDGE_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
# EVAL_SUBSET=15 makes CI score only the first 15 pairs to save time/cost.
EVAL_SUBSET = int(os.getenv("EVAL_SUBSET", "0")) or None

# Stable, human-friendly metric names mapped from Ragas' raw column names.
METRIC_COLUMNS = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "llm_context_precision_without_reference": "context_precision",
    "context_recall": "context_recall",
}
METRIC_NAMES = list(METRIC_COLUMNS.values())


def load_golden(path: Path = GOLDEN_PATH, subset: int | None = EVAL_SUBSET) -> list[dict]:
    """Load the golden eval pairs, optionally truncated to `subset` rows."""
    data = json.loads(path.read_text())
    if subset:
        data = data[:subset]
    return data


def call_rag(question: str, url: str = RAG_URL, timeout: int = 120) -> dict:
    """Call the FastAPI RAG endpoint. Raises on any HTTP / network error.

    Raising (instead of swallowing) is deliberate: a failed call must NOT be
    scored as an empty-context row, because that silently corrupts the metrics.
    """
    resp = requests.post(url, json={"question": question}, timeout=timeout)
    if not resp.ok:
        # Surface the server's actual error body (e.g. a Groq rate-limit
        # message) instead of a bare "500 Server Error" that hides the cause.
        raise RuntimeError(
            f"RAG endpoint returned HTTP {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    contexts = data.get("contexts") or []
    if not contexts:
        raise RuntimeError(f"RAG returned no contexts for: {question!r}")
    return {"answer": data["answer"], "contexts": contexts}


def build_dataset(golden: list[dict], strict: bool = True) -> Dataset:
    """Run every golden question through RAG and build the Ragas Dataset.

    strict=True  -> raise on the first RAG failure (use locally / in CI).
    strict=False -> skip failed rows (and report how many) but never insert
                    empty-context placeholder rows.
    """
    rows: dict[str, list] = {
        "user_input": [],
        "reference": [],
        "response": [],
        "retrieved_contexts": [],
    }
    failures = 0
    for i, ex in enumerate(golden):
        print(f"  [{i + 1}/{len(golden)}] {ex['question'][:60]}...")
        try:
            out = call_rag(ex["question"])
        except Exception as exc:  # noqa: BLE001
            failures += 1
            if strict:
                raise RuntimeError(
                    f"RAG call failed for id={ex.get('id')} — is the server up "
                    f"at {RAG_URL}? Original error: {exc}"
                ) from exc
            print(f"    skipped (error): {exc}")
            continue
        rows["user_input"].append(ex["question"])
        rows["reference"].append(ex["ground_truth"])
        rows["response"].append(out["answer"])
        rows["retrieved_contexts"].append(out["contexts"])

    if not rows["user_input"]:
        raise RuntimeError("No successful RAG calls — every row failed.")
    if failures:
        print(f"  WARNING: {failures} row(s) skipped due to RAG errors.")
    return Dataset.from_dict(rows)


def _make_judge() -> tuple[LangchainLLMWrapper, LangchainEmbeddingsWrapper]:
    """Build the judge LLM (Groq) and local embeddings used by Ragas."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set — cannot run the judge LLM.")
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=JUDGE_MODEL,
            temperature=0,
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
        )
    )
    # FastEmbed runs locally and for free — no OpenAI embedding bill.
    from langchain_community.embeddings import FastEmbedEmbeddings

    judge_emb = LangchainEmbeddingsWrapper(
        FastEmbedEmbeddings(model_name=JUDGE_EMBED_MODEL)
    )
    return judge_llm, judge_emb


def run_eval(golden: list[dict] | None = None, strict: bool = True) -> pd.DataFrame:
    """Full pipeline: golden -> RAG -> Ragas. Returns a per-row DataFrame.

    The DataFrame is guaranteed to have the four normalised metric columns:
    faithfulness, answer_relevancy, context_precision, context_recall.
    """
    golden = golden if golden is not None else load_golden()
    dataset = build_dataset(golden, strict=strict)
    judge_llm, judge_emb = _make_judge()

    # The judge runs on Groq's free tier, which rate-limits aggressively. The
    # default Ragas RunConfig fires 16 judge calls at once, which triggers a
    # 429 storm; jobs then hit the per-call timeout and come back as NaN
    # (notably context_recall). We dial concurrency down to reduce the storm
    # while keeping throughput reasonable, and add generous retries with
    # backoff so a 429 is retried rather than turned into a NaN.
    run_config = RunConfig(
        timeout=300,      # seconds per judge call
        max_retries=10,   # retry 429s instead of giving up
        max_wait=60,      # cap on exponential backoff between retries
        max_workers=4,    # fewer concurrent calls = fewer 429s
    )

    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithoutReference(),
            LLMContextRecall(),
        ],
        llm=judge_llm,
        embeddings=judge_emb,
        run_config=run_config,
    )
    df = result.to_pandas()
    # Normalise the metric column names to the stable set.
    df = df.rename(columns=METRIC_COLUMNS)
    return df


def mean_scores(df: pd.DataFrame) -> dict[str, float]:
    """Collapse the per-row DataFrame into one mean per metric (NaN-safe)."""
    return {name: float(df[name].mean()) for name in METRIC_NAMES if name in df}
