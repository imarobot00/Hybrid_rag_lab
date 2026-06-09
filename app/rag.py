"""End-to-end RAG pipeline used by the FastAPI app.

Multi-query expansion -> hybrid retrieval (dense + BM25 + RRF) -> dedupe ->
cross-encoder rerank -> grounded answer via Groq.

All heavy objects (embedders, reranker, Qdrant + Groq clients) are loaded ONCE
at module import time so each request is cheap.
"""
from __future__ import annotations

import logging

from fastembed import SparseTextEmbedding, TextEmbedding
from groq import Groq
from qdrant_client import QdrantClient, models
from sentence_transformers import CrossEncoder

from .settings import settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't know based on the provided notes."
Cite the source filename in square brackets at the end of relevant sentences.

Context:
{context}

Question: {question}

Answer:"""

# ── Heavy singletons (loaded once at import) ────────────────────────────────
logger.info("Loading dense embedder: %s", settings.dense_model)
_dense = TextEmbedding(model_name=settings.dense_model)

logger.info("Loading sparse embedder: %s", settings.sparse_model)
_sparse = SparseTextEmbedding(model_name=settings.sparse_model)

logger.info("Loading reranker: %s", settings.reranker_model)
_reranker = CrossEncoder(settings.reranker_model)

logger.info("Connecting to Qdrant: %s", settings.qdrant_url)
_qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

_groq = Groq(api_key=settings.groq_api_key)


# ── Step 1: query expansion ─────────────────────────────────────────────────
def expand_query(question: str, n: int | None = None) -> list[str]:
    n = n or settings.n_variants
    prompt = (
        f"Generate {n} different rephrasings of the following question. "
        f"Preserve the original meaning but use different wording. "
        f"Output ONLY the questions, one per line, no numbering, no dashes, no extra text.\n\n"
        f"Question: {question}"
    )
    response = _groq.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    text = response.choices[0].message.content or ""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines[:n]


# ── Step 2a: hybrid retrieve for ONE query ──────────────────────────────────
def hybrid_retrieve(query: str, limit: int) -> list:
    dense_vec = list(_dense.embed([query]))[0]
    sparse_vec = list(_sparse.embed([query]))[0]
    results = _qdrant.query_points(
        collection_name=settings.collection,
        prefetch=[
            models.Prefetch(
                query=dense_vec.tolist(),
                using="dense",
                limit=limit * 3,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="bm25",
                limit=limit * 3,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return results.points


# ── Step 2b: pool over all queries and dedupe by chunk_id ──────────────────
def multi_query_retrieve(queries: list[str]) -> list:
    seen: set[int] = set()
    pooled: list = []
    for q in queries:
        for h in hybrid_retrieve(q, settings.candidates):
            cid = h.payload.get("chunk_id")
            if cid not in seen:
                seen.add(cid)
                pooled.append(h)
    return pooled


# ── Step 3: cross-encoder rerank against the ORIGINAL question ─────────────
def rerank(question: str, points: list, top_k: int) -> list[dict]:
    if not points:
        return []
    pairs = [(question, p.payload.get("text", "")) for p in points]
    scores = _reranker.predict(pairs)
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


# ── Step 4: grounded answer via Groq ───────────────────────────────────────
def _build_context(hits: list[dict]) -> str:
    return "\n\n---\n\n".join(
        f"[{h['source']} #chunk{h['chunk_id']}]\n{h['text']}" for h in hits
    )


def generate_answer(question: str, hits: list[dict]) -> str:
    if not hits:
        return "I don't know based on the provided notes."
    prompt = PROMPT_TEMPLATE.format(
        context=_build_context(hits), question=question
    )
    response = _groq.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


# ── Public entrypoint ──────────────────────────────────────────────────────
def answer(question: str) -> dict:
    """Run the full pipeline and return the answer + provenance."""
    variants = expand_query(question)
    all_queries = [question] + variants
    pooled = multi_query_retrieve(all_queries)
    final = rerank(question, pooled, settings.top_k)
    text = generate_answer(question, final)
    return {
        "question": question,
        "answer": text,
        "variants": variants,
        "sources": [
            {"chunk_id": h["chunk_id"], "source": h["source"], "score": h["score"]}
            for h in final
        ],
        "pool_size": len(pooled),
    }
