"""Gate on answer relevance — does the answer actually address the question?

Answer relevance is high when the answer is on-topic and non-evasive, and low
when it rambles, pads, or dodges with "I don't know" when it shouldn't.
"""
from thresholds import THRESHOLDS  # type: ignore[import-not-found]


def test_answer_relevance_above_threshold(scores):
    score = scores["answer_relevancy"]
    threshold = THRESHOLDS["answer_relevancy"]
    assert score >= threshold, (
        f"answer_relevancy {score:.3f} < threshold {threshold} "
        f"(answers are evasive, padded, or off-topic)"
    )
