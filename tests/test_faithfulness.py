"""Gate on faithfulness — the anti-hallucination metric.

Faithfulness = fraction of claims in the answer that are supported by the
retrieved context. Low faithfulness means the model is inventing facts.
"""
from thresholds import THRESHOLDS  # type: ignore[import-not-found]


def test_faithfulness_above_threshold(scores):
    score = scores["faithfulness"]
    threshold = THRESHOLDS["faithfulness"]
    assert score >= threshold, (
        f"faithfulness {score:.3f} < threshold {threshold} "
        f"(the model is stating facts not in the retrieved context)"
    )
