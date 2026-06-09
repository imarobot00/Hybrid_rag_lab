# We will be using MultiQuery to retrieve from both dense and sparse fields in one call, then reranking with a cross-encoder.
# LLM (query expansion + final answer): Groq (llama-3.3-70b-versatile)
# Dense/Sparse embeddings: fastembed  ← must match what was used at index time (SDN collection)
# Reranker: CrossEncoder

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from groq import Groq

from fastembed import TextEmbedding, SparseTextEmbedding
from sentence_transformers import CrossEncoder
from qdrant_client import QdrantClient
from qdrant_client import models

# ── Constants ──────────────────────────────────────────────────────────────────
DENSE_MODEL_NAME    = "BAAI/bge-small-en-v1.5"   # MUST match what ingest.py used
SPARSE_MODEL_NAME   = "Qdrant/bm25"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_COLLECTION  = "SDN"
DEFAULT_TOP_K       = 5
CANDIDATES          = 25
LLM_MODEL           = "llama-3.3-70b-versatile"
N_VARIANTS          = 3     # how many paraphrases to generate

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't know based on the provided notes."
Cite the source filename in square brackets at the end of relevant sentences.

Context:
{context}

Question: {question}

Answer:"""

# ── Step 1: query expansion ────────────────────────────────────────────────────
def expand_query(groq_client: Groq, question: str, n: int = N_VARIANTS) -> list[str]:
    """Ask the LLM to rephrase `question` into `n` alternative versions.
    Returns a list of n strings (the paraphrases).
    The original question is NOT included — caller adds it separately.
    """
    prompt = (
        f"Generate {n} different rephrasings of the following question. "
        f"Preserve the original meaning but use different wording. "
        f"Output ONLY the questions, one per line, no numbering, no dashes, no extra text.\n\n"
        f"Question: {question}"
    )
    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,   # higher temp = more diverse paraphrases
    )
    text = response.choices[0].message.content
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines[:n]


if __name__ == "__main__":
    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY not found in environment (.env).")
    gc = Groq()
    q = "how does an OpenFlow controller program a switch?"
    variants = expand_query(gc, q)
    print("Original:", q)
    print("Variants:")
    for v in variants:
        print(" →", v)