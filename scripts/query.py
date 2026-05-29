"""Query both chunking-strategy collections and compare top-5 hits side by side.

Usage:
    uv run scripts/query.py                          # runs the built-in 10 queries on both collections
    uv run scripts/query.py --query "what is SDN"    # single query
    uv run scripts/query.py --collection notes_recursive_bge --query "..."
"""

from __future__ import annotations

import argparse
from typing import Iterable

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_COLLECTIONS = ["notes_recursive_bge", "notes_fixed_bge"]
TOP_K = 5

QUERIES = [
    "what is software-defined networking",
    "explain the OpenFlow protocol",
    "difference between control plane and data plane",
    "SDN three-layer architecture northbound southbound APIs",
    "SDN controller placement problem",
    "scalability challenges in SDN controllers",
    "what is the P4 programming language",
    "SDN security threats and attacks",
    "advantages of separating control and data planes",
    "how does an SDN switch handle a flow table miss",
]


def search(
    client: QdrantClient,
    model: SentenceTransformer,
    collection: str,
    query: str,
    top_k: int = TOP_K,
) -> list[dict]:
    qvec = model.encode(query).tolist()
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


def print_hits(label: str, hits: Iterable[dict]) -> None:
    print(f"  [{label}]")
    for i, h in enumerate(hits, 1):
        preview = " ".join(h["text"].split())[:150]
        print(f"    {i}. {h['score']:.4f}  {h['source']}#chunk{h['chunk_id']}  {preview}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="Run a single query instead of the built-in 10.")
    parser.add_argument(
        "--collection",
        action="append",
        help="Collection(s) to query. Repeatable. Defaults to both ingest variants.",
    )
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    collections = args.collection or DEFAULT_COLLECTIONS
    queries = [args.query] if args.query else QUERIES

    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(args.qdrant_url)

    for q in queries:
        print("=" * 100)
        print(f"Q: {q}")
        for coll in collections:
            hits = search(client, model, coll, q, args.top_k)
            print_hits(coll, hits)
        print()


if __name__ == "__main__":
    main()
