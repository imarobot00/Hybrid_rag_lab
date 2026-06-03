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
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_COLLECTION = "notes_recursive_bge"
DEFAULT_TOP_K = 5
LLM_MODEL = "llama-3.3-70b-versatile"

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't know based on the provided notes."
Cite the source filename in square brackets at the end of relevant sentences.

Context:
{context}

Question: {question}

Answer:"""


def retrieve(client: QdrantClient, embedder: SentenceTransformer, collection: str, question: str, top_k: int) -> list[dict]:
    qvec = embedder.encode(question).tolist()
    hits = client.query_points(
        collection_name=collection, query=qvec, limit=top_k, with_payload=True
    ).points
    return [
        {
            "score": h.score,
            "source": h.payload.get("source", "?"),
            "chunk_id": h.payload.get("chunk_id", -1),
            "text": h.payload.get("text", ""),
        }
        for h in hits
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

    embedder = SentenceTransformer(EMBED_MODEL)
    qclient = QdrantClient(args.qdrant_url)
    gclient = Groq()

    hits = retrieve(qclient, embedder, args.collection, args.question, args.top_k)
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
