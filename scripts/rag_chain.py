"""Minimal RAG: question -> retrieve from Qdrant -> Groq LLM writes the answer.

Usage:
    uv run scripts/rag_chain.py "What is OpenFlow?"
    uv run scripts/rag_chain.py "What is OpenFlow?" --collection notes_recursive_bge --top-k 5
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from groq import Groq
from qdrant_client import QdrantClient

from fastembed import TextEmbedding, SparseTextEmbedding
from sentence_transformers import CrossEncoder
from qdrant_client import models

DENSE_MODEL_NAME    = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME   = "Qdrant/bm25"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_COLLECTION  = "SDN"            # ← hybrid collection
DEFAULT_TOP_K       = 5
CANDIDATES          = 25               # over-fetch for reranker
LLM_MODEL           = "llama-3.3-70b-versatile"

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't know based on the provided notes."
Cite the source filename in square brackets at the end of relevant sentences.

Context:
{context}

Question: {question}

Answer:"""


def retrieve(
    client: QdrantClient,
    dense_embedder: TextEmbedding,
    sparse_embedder: SparseTextEmbedding,
    reranker: CrossEncoder,
    collection: str,
    question: str,
    top_k: int,
) -> list[dict]:
    # 1. Embed the question with both encoders.
    dense_vec  = list(dense_embedder.embed([question]))[0]
    sparse_vec = list(sparse_embedder.embed([question]))[0]

    # 2. Hybrid retrieve CANDIDATES results via RRF fusion (dense + BM25).
    fused = client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(
                query=dense_vec.tolist(),
                using="dense",
                limit=CANDIDATES,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="bm25",
                limit=CANDIDATES,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=CANDIDATES,
        with_payload=True,
    ).points

    # 3. Rerank the fused candidates with the cross-encoder.
    pairs = [(question, h.payload.get("text", "")) for h in fused]
    rerank_scores = reranker.predict(pairs)

    # 4. Sort by reranker score (desc) and take top_k.
    ranked = sorted(zip(fused, rerank_scores), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {
            "score": float(score),   # reranker score, not RRF
            "source": h.payload.get("source", "?"),
            "chunk_id": h.payload.get("chunk_id", -1),
            "text": h.payload.get("text", ""),
        }
        for h, score in ranked
    ]


def build_context(hits: list[dict]) -> str:
    blocks = []
    for h in hits:
        blocks.append(f"[source: {h['source']} #chunk{h['chunk_id']}]\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def generate(groq_client: Groq, question: str, context: str) -> str:
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    resp = groq_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Question to ask.")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--show-context", action="store_true", help="Print the retrieved chunks too.")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY not found in environment (.env).")

    dense_embedder  = TextEmbedding(model_name=DENSE_MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    reranker        = CrossEncoder(RERANKER_MODEL_NAME)
    qclient = QdrantClient(args.qdrant_url)
    gclient = Groq()

    hits = retrieve(
        qclient,
        dense_embedder,
        sparse_embedder,
        reranker,
        args.collection,
        args.question,
        args.top_k,
    )
    context = build_context(hits)

    if args.show_context:
        print("=" * 80)
        print("RETRIEVED CONTEXT")
        print("=" * 80)
        print(context)
        print()

    print("=" * 80)
    print(f"Q: {args.question}")
    print("=" * 80)
    answer = generate(gclient, args.question, context)
    print(answer)


if __name__ == "__main__":
    main()
