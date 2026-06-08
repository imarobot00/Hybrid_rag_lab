from __future__ import annotations

import argparse #to parse command-line arguments
import os
from fastembed import TextEmbedding, SparseTextEmbedding
from sentence_transformers import CrossEncoder

DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm25"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # ~90 MB, English, fast
reranker = CrossEncoder(RERANKER_MODEL_NAME)

from qdrant_client import QdrantClient
from qdrant_client import models
COLLECTION = "SDN"
CANDIDATES = 25   # how many fused hits to fetch before reranking

def main() -> None:

    parser = argparse.ArgumentParser() # Argument parser setup
    parser.add_argument("question", help="Question to ask.")
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    args = parser.parse_args() # Parse command-line arguments

    # load_dotenv() # (harmless even though we don't need a key yet)
    client = QdrantClient(args.qdrant_url)

    # Instantiate both embedders
    dense_embedder  = TextEmbedding(model_name=DENSE_MODEL_NAME)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

    
    # Embed the question with each.
    # .embed() expects a list and returns a generator -> list(...) materialises it.
    dense_vec  = list(dense_embedder.embed([args.question]))[0]
    sparse_vec = list(sparse_embedder.embed([args.question]))[0]

    

    # Sanity prints — confirms both encoders worked correctly before we search.
    print("dense  type:", type(dense_vec).__name__, " shape:", dense_vec.shape)
    print("sparse type:", type(sparse_vec).__name__)
    print("sparse indices (first 10):", sparse_vec.indices[:10])
    print("sparse values  (first 10):", sparse_vec.values[:10])
    print("sparse nonzero count:", len(sparse_vec.indices))

    # STEP 1: Hybrid search — send BOTH vectors to Qdrant in one request  #
    # `prefetch` tells Qdrant to run two independent searches server-side:
    #   branch A — dense cosine search using the "dense" vector index
    #   branch B — BM25 sparse search using the "bm25" vector index
    # Each branch fetches 3× top_k candidates (over-fetch so the fusion
    # has enough material to reorder from).
    results = client.query_points(
        collection_name=args.collection,
        prefetch=[
            # Branch A: dense (semantic) search
            models.Prefetch(
                query=dense_vec.tolist(),  # our 384-d query embedding as a plain list
                using="dense",             # name of the dense vector field in the collection
                limit=CANDIDATES,          # over-fetch before fusion
            ),
            # Branch B: BM25 (keyword) search
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),  # token ids
                    values=sparse_vec.values.tolist(),    # their weights
                ),
                using="bm25",             # name of the sparse vector field in the collection
                limit=CANDIDATES,
            ),
        ],
        # RRF (Reciprocal Rank Fusion) merges the two ranked lists.
        # It only cares about *rank*, not raw score, so the different
        # scales of cosine (~[-1,1]) and BM25 (~unbounded) don't matter.
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=CANDIDATES,    # final number of fused chunks (feed into reranker next step)
        with_payload=True,   # include the stored text + metadata in the response
    )

    # Print the retrieved chunks so we can verify retrieval quality        
    print(f"\n── Top {CANDIDATES} fused candidates for: '{args.question}' ──\n")
    for rank, hit in enumerate(results.points, start=1):
        print(f"[{rank}] score={hit.score:.4f}  source={hit.payload.get('source')}  chunk={hit.payload.get('chunk_id')}")
        # Print the first 300 chars of the chunk so we can eyeball relevance.
        print(f"    {hit.payload.get('text', '')[:300]}")
        print()
    
    print(f"Total hits returned: {len(results.points)}")

    # Build (query, chunk_text) pairs — one per candidate
    pairs = [(args.question, hit.payload["text"]) for hit in results.points]

    # Score them all in one batched call
    scores = reranker.predict(pairs)

    # pair up each chunk with its new score, then sort by it
    reranked = sorted(zip(results.points, scores), key=lambda x: x[1],
                        reverse=True)  # highest score first
    
    # Print final top-N
    TOP_N = 5
    print(f"\n══ Reranked top {TOP_N} ══\n")
    for rank, (hit, score) in enumerate(reranked[:TOP_N], start=1):
        print(f"[{rank}] rerank_score={score:.4f}  chunk={hit.payload.get('chunk_id')}")
        print(f"    {hit.payload.get('text','')[:300]}")
        print()




if __name__ == "__main__":
    main()