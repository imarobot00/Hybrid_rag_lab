"""Structured answer generation with citation verification.

This module does two jobs:
1. Ask the LLM for a structured answer with citations.
2. Verify that each citation's quoted text really appears in the retrieved chunks.

That second step is the integrity check. If a citation is not grounded in the
retrieved text, it gets dropped.
"""

from __future__ import annotations

import json
import os
import sys

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(__file__))
from parent_retriever import (  # reuse the retrieval + routing helpers
    LLM_MODEL,
    _get_groq,
    filters_to_qdrant,
    retrieve_baseline,
    self_query,
)


class Citation(BaseModel):
    source: str = Field(description="The source filename this quote came from.")
    quoted_span: str = Field(
        description="A short verbatim quote copied exactly from the retrieved chunk."
    )


class Answer(BaseModel):
    answer: str = Field(description="The final answer to the user's question.")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Supporting quotes copied verbatim from the context.",
    )


ANSWER_SYSTEM = """You answer questions using ONLY the provided context chunks.

Return a JSON object with exactly these keys:
{
  "answer": "<your answer, grounded only in the context>",
  "citations": [
    {"source": "<filename of the chunk>", "quoted_span": "<one sentence copied EXACTLY from that chunk>"}
  ]
}

Rules:
- Use ONLY information present in the context. If the context doesn't answer it, say so.
- Every quoted_span MUST be copied verbatim (character-for-character) from a chunk.
- Do not paraphrase quotes. Output JSON only."""


def generate_answer(question: str, chunks: list[dict]) -> Answer:
    """One LLM call → a structured Answer (citations not yet verified)."""
    context = "\n\n".join(
        f"[source: {c['source']}]\n{c['text']}" for c in chunks
    )
    resp = _get_groq().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return Answer.model_validate_json(raw)
    except Exception:
        return Answer(answer="(failed to parse model output)", citations=[])


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase so trivial formatting differences do not fail."""
    return " ".join(text.split()).lower()


def verify_citations(answer: Answer, chunks: list[dict]) -> Answer:
    """Drop any citation whose quoted_span does NOT literally appear in a chunk."""
    haystacks = [_normalize(c["text"]) for c in chunks]
    kept: list[Citation] = []
    for cit in answer.citations:
        needle = _normalize(cit.quoted_span)
        if needle and any(needle in hay for hay in haystacks):
            kept.append(cit)        # quote is real → keep
        # else: hallucinated quote → silently dropped
    return Answer(answer=answer.answer, citations=kept)


def answer_question(question: str, k: int = 5) -> tuple[dict, list[dict], Answer, Answer]:
    """Route, retrieve, answer, and verify in one place.

    Returns:
        parsed query info, retrieved chunks, raw Answer, verified Answer.
    """
    parsed = self_query(question)
    query_filter = filters_to_qdrant(parsed["filters"])
    chunks = retrieve_baseline(parsed["rewritten_query"], k, query_filter)
    raw_answer = generate_answer(question, chunks)
    verified_answer = verify_citations(raw_answer, chunks)
    return parsed, chunks, raw_answer, verified_answer


# ── Streaming answer ─────────────────────────────────────────────────────────
# Streaming and structured output fight each other: citation verification needs
# the COMPLETE text, but streaming hands out pieces before it is complete. So we
# stream plain prose for nice UX, then verify citations separately on the full text.
STREAM_SYSTEM = """You answer questions using ONLY the provided context chunks.
If the answer is not in the context, say you don't know based on the notes.
Cite the source filename in square brackets after the relevant sentence."""


def generate_answer_stream(question: str, chunks: list[dict]):
    """Yield the answer token by token (a generator) instead of one big string."""
    context = "\n\n".join(f"[source: {c['source']}]\n{c['text']}" for c in chunks)
    stream = _get_groq().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": STREAM_SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.0,
        stream=True,  # <-- the switch: response becomes an iterator of chunks
    )
    for chunk in stream:
        piece = chunk.choices[0].delta.content
        if piece:  # the final chunk's delta.content is None
            yield piece