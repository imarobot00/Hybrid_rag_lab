"""Ingest Section_*.md files into Qdrant with a pluggable chunker.

Usage:
    uv run scripts/ingest.py --chunker recursive --collection notes_recursive_bge
    uv run scripts/ingest.py --chunker fixed     --collection notes_fixed_bge
"""

from __future__ import annotations

import argparse
import glob
import os
import time
from typing import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient,models
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from fastembed import TextEmbedding, SparseTextEmbedding
import uuid

#model for embedding the text chunks, and chunking parameters
MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
EMBED_DIM = 384  # bge-small-en-v1.5 is 384-dimensional
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Chunker = Callable[[str], list[str]] # function that takes text and returns list of chunks


# def fixed_chunker(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
#     """Naive fixed-window chunker — slices by character count, ignores structure."""
#     step = size - overlap
#     return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size].strip()]

# RecursiveCharacterTextSplitter from LangChain — respects paragraph/sentence boundaries.
def recursive_chunker(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """LangChain RecursiveCharacterTextSplitter — respects paragraph/sentence boundaries."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    return splitter.split_text(text)



# CHUNKERS: dict[str, Chunker] = {
#     "fixed": fixed_chunker,
#     "recursive": recursive_chunker,
# }

# This function is not used in the current code, but can be useful for resetting the collection during development.
# def reset_collection(client: QdrantClient, name: str, dim: int) -> None:
#     if client.collection_exists(name):
#         client.delete_collection(name)
#     client.create_collection(
#         collection_name=name,
#         vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
#     )


def main() -> None:
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--chunker", choices=list(CHUNKERS), required=True)
    # parser.add_argument("--collection", required=True)
    # parser.add_argument(
    #     "--glob",
    #     default=os.path.join(os.path.dirname(__file__), "Section_*.md"),
    #     help="Glob pattern for source markdown files.",
    # )
    # parser.add_argument("--qdrant-url", default="http://localhost:6333")
    # args = parser.parse_args()

    # t0 = time.perf_counter()

    # files = sorted(glob.glob(args.glob))
    # if not files:
    #     raise SystemExit(f"No files matched: {args.glob}")

    # chunker = CHUNKERS[args.chunker]

    # all_chunks: list[str] = []
    # metadata: list[dict] = []
    # for path in files:
    #     with open(path, "r", encoding="utf-8") as f:
    #         text = f.read()
    #     chunks = chunker(text)
    #     source = os.path.basename(path)
    #     for idx, ch in enumerate(chunks):
    #         all_chunks.append(ch)
    #         metadata.append({"source": source, "chunk_id": idx, "text": ch})

    # print(f"Embedding {len(all_chunks)} chunks with {MODEL_NAME}...")
    # model = SentenceTransformer(MODEL_NAME)
    # vectors = model.encode(all_chunks, batch_size=64, show_progress_bar=True)

    # client = QdrantClient(args.qdrant_url)
    # # reset_collection(client, args.collection, EMBED_DIM)

    # points = [
    #     PointStruct(id=i, vector=v.tolist(), payload=meta)
    #     for i, (v, meta) in enumerate(zip(vectors, metadata))
    # ]
    # client.upsert(collection_name=args.collection, points=points)

    # elapsed = time.perf_counter() - t0
    # print(
    #     f"Ingested {len(all_chunks)} chunks from {len(files)} files "
    #     f"into '{args.collection}' (chunker={args.chunker}) in {elapsed:.2f} seconds"
    # )
    
    ## Initialize Qdrant client and print existing collections
    client = QdrantClient("http://localhost:6333")

    # Delete and recreate the collection so each run starts fresh.
    # recreate_collection() is deprecated — use this pattern instead.
    if client.collection_exists("SDN"):
        client.delete_collection("SDN")
    client.create_collection(
        collection_name="SDN",
        vectors_config={
            "dense": models.VectorParams(
                size=EMBED_DIM,                   # must match the embedding model (384 for bge-small)
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(
                modifier=models.Modifier.IDF,     # Qdrant applies IDF weighting server-side
            ),
        },
    )

    # Load and chunk the markdown file.
    with open("Section_B_SDN.md", "r", encoding="utf-8") as f:
        text = f.read()
    chunks = recursive_chunker(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

    # Instantiate both encoders (model names are strings, not objects).
    dense_embedder  = TextEmbedding(model_name=MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

    # Embed all chunks in one batch (faster than one-by-one).
    # .embed() returns a generator; list() materialises it.
    dense_vecs  = list(dense_embedder.embed(chunks))   # List[np.ndarray], shape [384]
    sparse_vecs = list(sparse_embedder.embed(chunks))  # List[SparseEmbedding]

    points = []
    for idx, (chunk, dv, sv) in enumerate(zip(chunks, dense_vecs, sparse_vecs)):
        points.append(
            PointStruct(
                id=idx,
                vector={
                    "dense": dv.tolist(),                     # numpy array → plain list
                    "bm25": models.SparseVector(              # BM25 sparse vector
                        indices=sv.indices.tolist(),
                        values=sv.values.tolist(),
                    ),
                },
                payload={"text": chunk, "source": "Section_B_SDN.md", "chunk_id": idx},
            )
        )

    client.upsert(collection_name="SDN", points=points)
    print(f"Ingested {len(chunks)} chunks into 'SDN' collection.")

    

if __name__ == "__main__":
    main()
