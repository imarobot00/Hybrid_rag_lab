"""Query both chunking-strategy collections and compare top-5 hits side by side.

Usage:
    uv run scripts/query.py                          # runs the built-in 10 queries on both collections
    uv run scripts/query.py --query "what is SDN"    # single query
    uv run scripts/query.py --collection notes_recursive_bge --query "..."
"""

from __future__ import annotations

import argparse
import re
from statistics import mean
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


_WORD_RE = re.compile(r"\w+")


def has_clean_start(text: str) -> bool:
    """True if chunk starts at a structural boundary (header, list, code fence, sentence)
    instead of mid-word/mid-sentence — proxy for chunk-quality."""
    stripped = text.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    if first in "#-*>|`" or first.isdigit():
        return True
    # Must start with a capital letter AND the original chunk shouldn't begin with a lowercase
    # word continuation (e.g. "ch configuration..." is bad).
    return first.isupper()


def tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def top5_overlap(hits_a: list[dict], hits_b: list[dict]) -> float:
    """Avg pairwise Jaccard between the concatenated top-5 texts of two collections."""
    text_a = " ".join(h["text"] for h in hits_a)
    text_b = " ".join(h["text"] for h in hits_b)
    return jaccard(text_a, text_b)


def compare(results: dict[str, list[list[dict]]], queries: list[str]) -> None:
    """results[collection] is a list (per query) of top-k hit dicts."""
    colls = list(results.keys())
    if len(colls) != 2:
        return

    a, b = colls
    print("=" * 100)
    print(f"COMPARISON: {a}  vs  {b}")
    print("=" * 100)

    # Per-query table
    print(f"{'#':>2}  {'top1_'+a[:18]:>22}  {'top1_'+b[:18]:>22}  {'winner':>10}  {'overlap':>8}  query")
    a_wins = b_wins = ties = 0
    overlaps = []
    for i, q in enumerate(queries):
        ha, hb = results[a][i], results[b][i]
        sa, sb = ha[0]["score"], hb[0]["score"]
        ov = top5_overlap(ha, hb)
        overlaps.append(ov)
        if abs(sa - sb) < 1e-6:
            winner = "tie"
            ties += 1
        elif sa > sb:
            winner = a[:10]
            a_wins += 1
        else:
            winner = b[:10]
            b_wins += 1
        print(f"{i+1:>2}  {sa:>22.4f}  {sb:>22.4f}  {winner:>10}  {ov:>8.2f}  {q[:50]}")

    # Aggregate metrics
    def agg(coll: str) -> dict:
        all_hits = results[coll]
        top1_scores = [h[0]["score"] for h in all_hits]
        top5_scores = [s["score"] for h in all_hits for s in h]
        clean_top1 = sum(has_clean_start(h[0]["text"]) for h in all_hits)
        return {
            "avg_top1": mean(top1_scores),
            "avg_top5": mean(top5_scores),
            "clean_top1_rate": clean_top1 / len(all_hits),
        }

    print()
    print(f"{'metric':<20}  {a:>24}  {b:>24}")
    ma, mb = agg(a), agg(b)
    for k in ("avg_top1", "avg_top5", "clean_top1_rate"):
        print(f"{k:<20}  {ma[k]:>24.4f}  {mb[k]:>24.4f}")
    print(f"{'top1_wins':<20}  {a_wins:>24}  {b_wins:>24}    (ties: {ties})")
    print(f"{'avg_top5_overlap':<20}  {mean(overlaps):>24.4f}    (1.0 = identical results)")


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

    results: dict[str, list[list[dict]]] = {c: [] for c in collections}
    for q in queries:
        print("=" * 100)
        print(f"Q: {q}")
        for coll in collections:
            hits = search(client, model, coll, q, args.top_k)
            results[coll].append(hits)
            print_hits(coll, hits)
        print()

    if len(collections) == 2:
        compare(results, queries)


if __name__ == "__main__":
    main()
