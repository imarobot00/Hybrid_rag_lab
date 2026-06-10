"""Gate on context precision — is the retrieved context clean and well-ranked?

Context precision is high when the relevant chunks are retrieved AND ranked near
the top, and low when the retriever pads the context with irrelevant chunks.
"""
from thresholds import THRESHOLDS  # type: ignore[import-not-found]


def test_context_precision_above_threshold(scores):
    score = scores["context_precision"]
    threshold = THRESHOLDS["context_precision"]
    assert score >= threshold, (
        f"context_precision {score:.3f} < threshold {threshold} "
        f"(retriever is surfacing irrelevant chunks — lower top_k or tune rerank)"
    )
