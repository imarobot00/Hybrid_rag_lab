"""Parent-document retriever — small chunks for *search*, big chunks for *context*.

Pattern
-------
Small chunks (200 tokens) are precise: a dense/BM25 hit on a 200-token window
pinpoints the exact sentence that answers a question. But a 200-token window is
a poor thing to feed an LLM — it lacks surrounding context. So we index two
linked collections:

    chunks_small  — 200-token windows, searchable (dense + bm25). Each small
                    chunk's payload carries a `parent_id`.
    chunks_parent — 1000-token windows, NOT searched. Fetched by id and used as
                    the answer context.

Retrieval: search `chunks_small` -> collect distinct `parent_id`s in rank order
-> fetch those parents from `chunks_parent` -> return the parent texts.

This module is both:
    * a CLI ingest script:  uv run python scripts/parent_retriever.py
    * an importable library: `retrieve_with_parents(query, k)` and the flat
      baseline `retrieve_baseline(query, k)` are reused by eval/evaluate.py.
"""
from __future__ import annotations

import glob
import os
import time

from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models

MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
EMBED_DIM = 384

PARENT_TOKENS = 1000
SMALL_TOKENS = 200
SMALL_OVERLAP = 40

SMALL_COLLECTION = "chunks_small"
PARENT_COLLECTION = "chunks_parent"
BASELINE_COLLECTION = "notes_all"

DATA_GLOB = os.path.join(os.path.dirname(__file__), "data", "Section_*.md")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# ── Shared singletons (loaded once on import; matches app/rag.py pattern) ────
_dense = TextEmbedding(model_name=MODEL_NAME)
_sparse = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
_client = QdrantClient(url=QDRANT_URL)


# ── Token-aware splitters ───────────────────────────────────────────────────
def _splitters() -> tuple[RecursiveCharacterTextSplitter, RecursiveCharacterTextSplitter]:
    """Build token-counting recursive splitters using the bge tokenizer.

    Splitting by *tokens* (not chars) makes the 200/1000 budgets honest, since
    that is the unit the embedding model actually consumes.
    """
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    parent = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tok, chunk_size=PARENT_TOKENS, chunk_overlap=0
    )
    small = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tok, chunk_size=SMALL_TOKENS, chunk_overlap=SMALL_OVERLAP
    )
    return parent, small


# ── Ingest ──────────────────────────────────────────────────────────────────
def build() -> None:
    t0 = time.perf_counter()
    files = sorted(glob.glob(DATA_GLOB))
    if not files:
        raise SystemExit(f"No files matched: {DATA_GLOB}")

    parent_splitter, small_splitter = _splitters()

    parent_texts: list[str] = []
    parent_payloads: list[dict] = []
    small_texts: list[str] = []
    small_payloads: list[dict] = []

    parent_id = 0
    small_id = 0
    for path in files:
        source = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for parent_chunk in parent_splitter.split_text(text):
            parent_texts.append(parent_chunk)
            parent_payloads.append(
                {"text": parent_chunk, "source": source, "parent_id": parent_id}
            )
            # Each small chunk maps to exactly ONE parent.
            for small_chunk in small_splitter.split_text(parent_chunk):
                small_texts.append(small_chunk)
                small_payloads.append(
                    {
                        "text": small_chunk,
                        "source": source,
                        "parent_id": parent_id,
                        "chunk_id": small_id,
                    }
                )
                small_id += 1
            parent_id += 1

    print(
        f"Built {len(parent_texts)} parent chunks ({PARENT_TOKENS} tok) and "
        f"{len(small_texts)} small chunks ({SMALL_TOKENS} tok) from {len(files)} files."
    )

    # --- chunks_small: hybrid (dense + bm25), searchable -------------------
    print(f"Embedding {len(small_texts)} small chunks (dense + bm25)...")
    small_dense = list(_dense.embed(small_texts))
    small_sparse = list(_sparse.embed(small_texts))

    if _client.collection_exists(SMALL_COLLECTION):
        _client.delete_collection(SMALL_COLLECTION)
    _client.create_collection(
        collection_name=SMALL_COLLECTION,
        vectors_config={
            "dense": models.VectorParams(size=EMBED_DIM, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    small_points = [
        models.PointStruct(
            id=p["chunk_id"],
            vector={
                "dense": dv.tolist(),
                "bm25": models.SparseVector(
                    indices=sv.indices.tolist(), values=sv.values.tolist()
                ),
            },
            payload=p,
        )
        for p, dv, sv in zip(small_payloads, small_dense, small_sparse)
    ]
    _client.upsert(collection_name=SMALL_COLLECTION, points=small_points)

    # --- chunks_parent: dense only, fetched by id (never searched) ---------
    print(f"Embedding {len(parent_texts)} parent chunks (dense, fetch-by-id)...")
    parent_dense = list(_dense.embed(parent_texts))
    if _client.collection_exists(PARENT_COLLECTION):
        _client.delete_collection(PARENT_COLLECTION)
    _client.create_collection(
        collection_name=PARENT_COLLECTION,
        vectors_config=models.VectorParams(size=EMBED_DIM, distance=models.Distance.COSINE),
    )
    parent_points = [
        models.PointStruct(id=p["parent_id"], vector=dv.tolist(), payload=p)
        for p, dv in zip(parent_payloads, parent_dense)
    ]
    _client.upsert(collection_name=PARENT_COLLECTION, points=parent_points)

    elapsed = time.perf_counter() - t0
    print(
        f"\nIngested '{SMALL_COLLECTION}' ({len(small_points)}) + "
        f"'{PARENT_COLLECTION}' ({len(parent_points)}) in {elapsed:.1f}s."
    )


# ── Query-time helpers (imported by eval/evaluate.py) ───────────────────────
def _hybrid_search(collection: str, query: str, limit: int) -> list:
    dense_vec = list(_dense.embed([query]))[0]
    sparse_vec = list(_sparse.embed([query]))[0]
    res = _client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(query=dense_vec.tolist(), using="dense", limit=limit * 3),
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
    return res.points


def retrieve_baseline(query: str, k: int = 5) -> list[dict]:
    """Flat hybrid retrieval over `notes_all` — returns top-k chunks."""
    points = _hybrid_search(BASELINE_COLLECTION, query, k)
    return [
        {
            "source": p.payload.get("source", "?"),
            "chunk_id": p.payload.get("chunk_id", -1),
            "text": p.payload.get("text", ""),
            "score": float(p.score),
        }
        for p in points
    ]


def retrieve_with_parents(query: str, k: int = 5, search_limit: int = 20) -> list[dict]:
    """Parent-document retrieval.

    Search small chunks, collect distinct parent ids in rank order, then fetch
    and return the top-k parent documents.
    """
    hits = _hybrid_search(SMALL_COLLECTION, query, search_limit)

    ordered_parents: list[int] = []
    seen: set[int] = set()
    for h in hits:
        pid = h.payload.get("parent_id")
        if pid is not None and pid not in seen:
            seen.add(pid)
            ordered_parents.append(pid)
        if len(ordered_parents) >= k:
            break

    if not ordered_parents:
        return []

    records = _client.retrieve(
        collection_name=PARENT_COLLECTION,
        ids=ordered_parents,
        with_payload=True,
    )
    by_id = {r.id: r for r in records}
    out: list[dict] = []
    for rank, pid in enumerate(ordered_parents):
        rec = by_id.get(pid)
        if rec is None:
            continue
        out.append(
            {
                "source": rec.payload.get("source", "?"),
                "parent_id": pid,
                "text": rec.payload.get("text", ""),
                "rank": rank,
            }
        )
    return out


if __name__ == "__main__":
    build()
