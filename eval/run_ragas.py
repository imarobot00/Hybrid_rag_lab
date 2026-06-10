"""Run the golden eval set through the RAG API and score with Ragas.

Usage (make sure the FastAPI server is running first):
    uv run python eval/run_ragas.py

What this does:
    1. Loads the 20 golden question/answer pairs from eval/golden_set.json
    2. Calls POST /query for each question (gets answer + contexts)
    3. Feeds everything to Ragas (the LLM judge scores it)
    4. Prints mean scores for faithfulness, answer relevance, context precision, context recall
    5. Saves per-row results to eval/last_run.json
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithoutReference,
    LLMContextRecall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Load .env so we can read GROQ_API_KEY
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
RAG_URL = "http://localhost:8000/query"
GOLDEN_PATH = Path(__file__).parent / "golden_set.json"
OUTPUT_PATH = Path(__file__).parent / "last_run.json"

# We use Groq as the judge via its OpenAI-compatible endpoint.
# This is FREE and avoids paying OpenAI for scoring.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Use 8b-instant for fast iteration (higher rate limits: 6000 RPM, 6M TPD)
# Switch to llama-3.3-70b-versatile for final "official" runs
JUDGE_MODEL = "llama-3.1-8b-instant"


def load_golden() -> list[dict]:
    """Load the golden eval set from disk."""
    return json.loads(GOLDEN_PATH.read_text())


def call_rag(question: str) -> dict:
    """Call our FastAPI RAG endpoint and return answer + contexts."""
    resp = requests.post(RAG_URL, json={"question": question}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return {
        "answer": data["answer"],
        "contexts": data["contexts"],  # list[str] — the raw chunk texts
    }


def build_dataset(golden: list[dict]) -> Dataset:
    """Run every golden question through RAG and build the Ragas Dataset."""
    rows = {
        "user_input": [],
        "reference": [],
        "response": [],
        "retrieved_contexts": [],
    }

    for i, ex in enumerate(golden):
        print(f"  [{i+1}/{len(golden)}] {ex['question'][:60]}...")
        try:
            out = call_rag(ex["question"])
            rows["user_input"].append(ex["question"])
            rows["reference"].append(ex["ground_truth"])
            rows["response"].append(out["answer"])
            rows["retrieved_contexts"].append(out["contexts"])
        except Exception as e:
            print(f"    ⚠ FAILED: {e}")
            # Still include it with empty values so indices align
            rows["user_input"].append(ex["question"])
            rows["reference"].append(ex["ground_truth"])
            rows["response"].append(f"ERROR: {e}")
            rows["retrieved_contexts"].append([])

    return Dataset.from_dict(rows)


def main():
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("RAG EVALUATION — Week 4")
    print("=" * 60)

    # Step 1: Load golden set
    golden = load_golden()
    print(f"\n✓ Loaded {len(golden)} golden eval pairs")

    # Step 2: Run all questions through the RAG pipeline
    print(f"\n→ Calling RAG API at {RAG_URL}...")
    dataset = build_dataset(golden)
    print(f"✓ Got answers for all {len(golden)} questions")

    # Step 3: Set up the LLM judge (Groq, free!)
    print(f"\n→ Setting up judge LLM: {JUDGE_MODEL} via Groq...")
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=JUDGE_MODEL,
            temperature=0,
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
        )
    )
    # For embeddings (needed by answer relevancy), use a local model
    # We'll use the same fastembed model we already have
    from langchain_community.embeddings import FastEmbedEmbeddings

    judge_emb = LangchainEmbeddingsWrapper(
        FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    )

    # Step 4: Run Ragas evaluation
    print("\n→ Running Ragas evaluation (this calls the judge LLM)...")
    metrics = [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextPrecisionWithoutReference(),
        LLMContextRecall(),
    ]

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_emb,
    )

    # Step 5: Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(result)

    df = result.to_pandas()
    df.to_json(str(OUTPUT_PATH), orient="records", indent=2)
    print(f"\n✓ Per-row results saved to {OUTPUT_PATH}")

    # Print summary stats
    score_cols = [c for c in df.columns if c not in ("user_input", "reference", "response", "retrieved_contexts")]
    if score_cols:
        print("\n" + df[score_cols].describe().to_string())


if __name__ == "__main__":
    main()
