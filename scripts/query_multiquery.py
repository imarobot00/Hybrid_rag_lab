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

# ── Step 2a: hybrid retrieve for ONE query (reuse from query_hybrid.py) ────────
def hybrid_retrieve(
    client: QdrantClient,
    dense_embedder: TextEmbedding,
    sparse_embedder: SparseTextEmbedding,
    collection: str,
    query: str,
    limit: int,
) -> list:
    """Run hybrid (dense + BM25 + RRF) retrieval for ONE query string.
    Returns the raw `points` list from Qdrant (each is a ScoredPoint).
    """
    # 1. Embed the query with both dense and sparse encoders.
    dense_vec  = list(dense_embedder.embed([query]))[0]
    sparse_vec = list(sparse_embedder.embed([query]))[0]

    # 2. Run a single Qdrant query with `prefetch` to search both indexes,
    #    then fuse the two ranked lists with RRF.
    results = client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(
                query=dense_vec.tolist(),
                using="dense",
                limit=limit * 3,   # over-fetch before fusion
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="bm25",
                limit=limit * 3,   # over-fetch before fusion
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),  # merge the two prefetches
        limit=limit,            # final number of fused hits
        with_payload=True,      # we need payload['chunk_id'] downstream
    )
    return results.points
    
    


# ── Step 2b: run hybrid retrieval for ALL queries and dedupe ──────────────────
def multi_query_retrieve(
    client: QdrantClient,
    dense_embedder: TextEmbedding,
    sparse_embedder: SparseTextEmbedding,
    collection: str,
    queries: list[str],
    per_query_limit: int = CANDIDATES,
) -> list:
    """Run hybrid_retrieve for each query in `queries`. Pool all hits
    and drop duplicates by chunk_id. Return the deduped list of points.
    """
    all_hits = []
    seen_chunk_ids = set()
    for q in queries:
        hits = hybrid_retrieve(client, dense_embedder, sparse_embedder, collection, q, per_query_limit)
        for h in hits:
            chunk_id = h.payload.get("chunk_id")
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                all_hits.append(h)
    return all_hits
    
def rerank(reranker: CrossEncoder, question: str, points: list, top_k: int) -> list[dict]:
    """Score each candidate point against the ORIGINAL question and return top_k.
    Uses the question (not the paraphrases) so the reranker judges relevance
    against what the user actually asked.
    """
    pairs = [(question, p.payload.get("text", "")) for p in points]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(points, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {
            "score": float(score),
            "source": p.payload.get("source", "?"),
            "chunk_id": p.payload.get("chunk_id", -1),
            "text": p.payload.get("text", ""),
        }
        for p, score in ranked
    ]

def build_context(hits: list[dict]) -> str:
    """Concatenate top-k chunks into a single context string with source markers
    so the LLM can cite them in its answer.
    """
    parts = []
    for h in hits:
        marker = f"[{h['source']} #chunk{h['chunk_id']}]"
        parts.append(f"{marker}\n{h['text']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(groq_client: Groq, question: str, hits: list[dict]) -> str:
    """Call Groq with PROMPT_TEMPLATE and the reranked top-k context.
    Uses temperature=0 for deterministic, faithful answers (different from
    the temperature=0.7 used during query expansion).
    """
    context = build_context(hits)
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY not found in environment (.env).")

    gc = Groq()
    qclient = QdrantClient("http://localhost:6333")
    dense_embedder  = TextEmbedding(model_name=DENSE_MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    reranker        = CrossEncoder(RERANKER_MODEL_NAME)   # ← NEW

    q = "how does an OpenFlow controller program a switch?"

    variants = expand_query(gc, q)
    all_queries = [q] + variants
    print(f"Querying with {len(all_queries)} variants:")
    for v in all_queries:
        print(" →", v)

    pooled = multi_query_retrieve(
        qclient, dense_embedder, sparse_embedder,
        DEFAULT_COLLECTION, all_queries,
    )
    print(f"\nPool: {len(pooled)} unique chunks (after dedupe)")

    # Rerank against the ORIGINAL question
    final = rerank(reranker, q, pooled, DEFAULT_TOP_K)

    print(f"\n══ Reranked top {DEFAULT_TOP_K} ══")
    for i, h in enumerate(final, 1):
        print(f"[{i}] rerank_score={h['score']:.4f}  chunk={h['chunk_id']}  source={h['source']}")
        print(f"    {h['text'][:200]}")
        print()
        # ── Step 4: generate the grounded answer ─────────────────────────────────
    answer = generate_answer(gc, q, final)
    print("\n══ Answer ══")
    print(answer)