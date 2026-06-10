"""Quality thresholds for the RAG eval suite.

These are deliberately LENIENT first-version floors. Ratchet them UP as the
system genuinely improves so they always encode "do not get worse than now".
A red build everyone ignores is worse than no build.
"""
THRESHOLDS = {
    "faithfulness": 0.80,        # anti-hallucination: answer grounded in context
    "answer_relevancy": 0.80,    # answer actually addresses the question
    "context_precision": 0.70,   # retrieved chunks are relevant / well-ranked
    "context_recall": 0.50,      # retrieved context covers the needed facts
}

# Regression tolerance: fail if any metric drops more than this vs the baseline.
MAX_REGRESSION_DROP = 0.03  # 3 points
