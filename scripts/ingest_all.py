"""Ingest ALL six Section_*.md notes into one Qdrant collection (`notes_all`).

This is the *baseline* corpus for Week-5 retrieval work. Until now only
`Section_B_SDN.md` lived in the `SDN` collection; this script loads the full
six-section corpus so the retriever has to discriminate between SDN and the
five neighbouring topics (IPv6, IoT/WSN, SDN-5G, migration, SDN-security).

Chunking matches the existing app pipeline (recursive, 500-char / 100-overlap)
and the same hybrid named-vector scheme (`dense` + `bm25`) so the FastAPI app
could point at this collection unchanged.

Usage (from project root):
    uv run python scripts/ingest_all.py
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
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
COLLECTION = "notes_all"

DATA_GLOB = os.path.join(os.path.dirname(__file__), "data", "Section_*.md")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def recursive_chunker(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    return splitter.split_text(text)


def main() -> None:
    t0 = time.perf_counter()

    files = sorted(glob.glob(DATA_GLOB))
    if not files:
        raise SystemExit(f"No files matched: {DATA_GLOB}")
    print(f"Found {len(files)} source files:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    chunks: list[str] = []
    payloads: list[dict] = []
    for path in files:
        source = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for local_idx, ch in enumerate(recursive_chunker(text)):
            payloads.append(
                {"text": ch, "source": source, "local_chunk_id": local_idx}
            )
            chunks.append(ch)

    print(f"\nEmbedding {len(chunks)} chunks with {MODEL_NAME}...")
    dense_embedder = TextEmbedding(model_name=MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    dense_vecs = list(dense_embedder.embed(chunks))
    sparse_vecs = list(sparse_embedder.embed(chunks))

    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size=EMBED_DIM, distance=models.Distance.COSINE
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
    )

    points = []
    for gid, (payload, dv, sv) in enumerate(zip(payloads, dense_vecs, sparse_vecs)):
        payload = {**payload, "chunk_id": gid}
        points.append(
            models.PointStruct(
                id=gid,
                vector={
                    "dense": dv.tolist(),
                    "bm25": models.SparseVector(
                        indices=sv.indices.tolist(),
                        values=sv.values.tolist(),
                    ),
                },
                payload=payload,
            )
        )

    client.upsert(collection_name=COLLECTION, points=points)
    elapsed = time.perf_counter() - t0
    print(
        f"\nIngested {len(points)} chunks from {len(files)} files into "
        f"'{COLLECTION}' in {elapsed:.1f}s."
    )


if __name__ == "__main__":
    main()
