"""Query rewriting — clean up a raw user question before it hits the retriever.

A query rewriter takes a vague / pronoun-heavy question and rewrites it into a
sharper search query (e.g. "how does it work?" -> "how does the OpenFlow
controller process a packet with no matching flow rule?"). It helps most on
ambiguous queries and should NEVER hurt queries that already retrieve well.

================================================================================
TODAY'S STRESS TEST — 10 golden_set.json IDs
================================================================================
We measure the rewriter against a fixed 10-query set, in two groups.

GROUP A — 5 HARD queries (reasoning/synthesis, keyword-rich).
  These already retrieve correctly (recall@5 = 1.00 on 2026-06-15). They are
  the GUARDRAIL: rewriting must not make these worse.
    sdn-004  Why is the Controller Placement Problem (CPP) NP-hard?
    sdn-007  How does a Genetic Algorithm solve the Multi-Controller Placement Problem?
    sdn-013  Key differences between P4_14 and P4_16?
    sdn-018  What makes ISP/Telco SDN deployment different from data center?
    sdn-032  How does K-Center differ from K-Median for controller placement?

GROUP B — 5 AMBIGUOUS queries (short / vague / open-ended referents).
  Vaguest questions in the set — where rewriting should HELP.
    sdn-006  What are the main scalability challenges in SDN control planes?
    sdn-021  What is the core idea that distinguishes SDN from a traditional network?
    sdn-022  Which analogy is used to describe SDN versus a traditional network?
    sdn-030  What analogy is used to explain the Controller Placement Problem?
    sdn-040  What are some emerging research directions in SDN?

NOTE: golden_set.json contains no truly short / pronoun-heavy queries (they are
all well-formed exam questions). Group B is the closest approximation. For a
stronger ambiguity stress test, hand-write *degraded* versions of these (e.g.
"how does it work?", "what's the difference?") and add them here later.
================================================================================
"""

from __future__ import annotations

import argparse
import os
import json
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
# Use the FULL 6-section corpus, not "SDN" (which only holds Section_B). With a
# single-source collection every hit is trivially "correct", so the recall test
# can't tell whether rewriting helps — notes_all forces the retriever to
# discriminate SDN from five neighbouring topics.
DEFAULT_COLLECTION  = "notes_all"
DEFAULT_TOP_K       = 5
# We RETRIEVE/rerank to top-5 but SCORE recall at this shallower depth. recall@5
# saturates at 1.00 on this corpus (the right source is always somewhere in the
# top 5), so it can't reveal whether rewriting helps. recall@1 has real headroom
# (~0.86 baseline) and is what actually moves when ranking improves.
SCORE_K             = 1
CANDIDATES          = 25
# Toggle to isolate the reranker's contribution. When False we skip the
# cross-encoder and rank pooled candidates by their Qdrant RRF fusion score
# instead — this shows what retrieval ordering ALONE achieves, and whether
# query rewriting moves the needle without a reranker masking the effect.
USE_RERANKER        = False
LLM_MODEL           = "llama-3.3-70b-versatile"
N_VARIANTS          = 3     # how many paraphrases to generate

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't know based on the provided notes."
Cite the source filename in square brackets at the end of relevant sentences.

Context:
{context}

Question: {question}

Answer:"""

STRESS_TEST_IDS = [
    # Group A — hard (guardrail)
    "sdn-004",
    "sdn-007",
    "sdn-013",
    "sdn-018",
    "sdn-032",
    # Group B — ambiguous (opportunity)
    "sdn-006",
    "sdn-021",
    "sdn-022",
    "sdn-030",
    "sdn-040",
]

"""Evaluation: recall@5 on a fixed set of 10 questions."""

##--------Using MultiQuery Retrieval as the rewriter's stress test-----------------------------

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


# ── Step 3: cross-encoder rerank to the final top-k ───────────────────────────
def rerank(reranker: CrossEncoder, question: str, points: list, top_k: int = DEFAULT_TOP_K) -> list:
    """Score every pooled chunk against the ORIGINAL question with the
    cross-encoder and keep only the best `top_k`. "recall@5" means the top 5,
    so we must trim the 30-40 pooled candidates down — that is this step's job.
    """
    if not points:
        return []
    pairs = [(question, p.payload.get("text", "")) for p in points]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(points, scores), key=lambda x: x[1], reverse=True)
    return [p for p, _ in ranked[:top_k]]


# ── Step 4: source-level recall@k for ONE question ────────────────────────────
def hit_at_k(points: list, want_source: str, k: int = DEFAULT_TOP_K) -> bool:
    """True if any of the top-k reranked chunks comes from `want_source`.
    Source-level match: a question is "found" if its home document appears.
    """
    sources = [p.payload.get("source", "?") for p in points[:k]]
    return want_source in sources


def retrieve_and_score(
    client, dense_embedder, sparse_embedder, reranker,
    queries: list[str], original_question: str, want_source: str,
) -> bool:
    """Full pipeline for one variant set: pool -> (rerank | RRF-sort) -> hit@SCORE_K?

    With USE_RERANKER=True the cross-encoder picks the top-k. With it False we
    fall back to ordering by the Qdrant fusion score, so 'top-1' is still a real
    relevance ranking (not just pooling insertion order).
    """
    pooled = multi_query_retrieve(
        client, dense_embedder, sparse_embedder, DEFAULT_COLLECTION, queries
    )
    if USE_RERANKER:
        top = rerank(reranker, original_question, pooled, DEFAULT_TOP_K)
    else:
        top = sorted(pooled, key=lambda p: p.score, reverse=True)[:DEFAULT_TOP_K]
    return hit_at_k(top, want_source, SCORE_K)


#Retriving the Questions from the golden_set.json file and then applying the multi_query_retrieve function on them to get the retrieved chunks for each question.
#Then we will print the retrieved chunks for each question vs Original Question to verify the retrieval quality.

if __name__ == "__main__":
    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY not found in environment (.env).")

    # Load the golden set and keep our 10 stress-test items (id, question,
    # and source_document — the label we score against).
    with open("../eval/golden_set.json", "r") as f:
        golden_set = json.load(f)
    items = [it for it in golden_set if it["id"] in STRESS_TEST_IDS]
    print(f"Loaded {len(items)} questions for stress testing.\n")

    # Initialise everything ONCE (clients/models are expensive to build).
    groq_client = Groq()
    client = QdrantClient("http://localhost:6333")
    dense_embedder = TextEmbedding(model_name=DENSE_MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    # Only load the cross-encoder if we're actually going to use it.
    reranker = CrossEncoder(RERANKER_MODEL_NAME) if USE_RERANKER else None
    print(f"Reranker: {'ON (cross-encoder)' if USE_RERANKER else 'OFF (RRF-score order)'}\n")

    # Which IDs belong to which group, so we can summarise A vs B separately.
    group_a = set(STRESS_TEST_IDS[:5])   # hard (guardrail)

    base_hits = rewrite_hits = 0
    a_base = a_rewrite = b_base = b_rewrite = 0

    for it in items:
        qid, question, want = it["id"], it["question"], it["source_document"]

        # BEFORE: original query only (no rewriting).
        base_hit = retrieve_and_score(
            client, dense_embedder, sparse_embedder, reranker,
            [question], question, want,
        )
        # AFTER: original query + LLM rewrites pooled together.
        variants = expand_query(groq_client, question)
        rewrite_hit = retrieve_and_score(
            client, dense_embedder, sparse_embedder, reranker,
            [question] + variants, question, want,
        )

        base_hits += base_hit
        rewrite_hits += rewrite_hit
        if qid in group_a:
            a_base += base_hit
            a_rewrite += rewrite_hit
        else:
            b_base += base_hit
            b_rewrite += rewrite_hit

        delta = (
            "REGRESSED" if base_hit and not rewrite_hit
            else "improved" if not base_hit and rewrite_hit
            else "same"
        )
        grp = "A-hard " if qid in group_a else "B-ambig"
        print(
            f"[{grp}] {qid}  before={'HIT ' if base_hit else 'MISS'} "
            f"after={'HIT ' if rewrite_hit else 'MISS'}  ({delta})"
        )

    n = len(items)
    print("\n" + "=" * 60)
    print(f"recall@{SCORE_K}  (source-level, over {n} stress-test Qs)")
    print("=" * 60)
    print(f"  ALL        before {base_hits}/{n} = {base_hits / n:.2f}   "
          f"after {rewrite_hits}/{n} = {rewrite_hits / n:.2f}")
    print(f"  A (hard)   before {a_base}/5 = {a_base / 5:.2f}   "
          f"after {a_rewrite}/5 = {a_rewrite / 5:.2f}   "
          f"{'(guardrail OK)' if a_rewrite >= a_base else '(!! REGRESSED)'}")
    print(f"  B (ambig)  before {b_base}/5 = {b_base / 5:.2f}   "
          f"after {b_rewrite}/5 = {b_rewrite / 5:.2f}   "
          f"{'(helped)' if b_rewrite > b_base else '(no gain)'}")
