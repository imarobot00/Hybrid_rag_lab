"""Structured answer with verifiable citations.

The LLM must return an Answer whose every Citation quotes text that LITERALLY
appears in a retrieved chunk. Citations that fail this check are dropped — that
is the integrity guarantee against hallucinated sources.
"""

from __future__ import annotations
from pydantic import BaseModel, Field #to define the schema of the answer and citation

class Citation(BaseModel):
    # This is the schema for a single citation in the answer. It includes the source filename and a quoted span from the retrieved chunk.
    source: str = Field(description="The source filename this quote came from.")
    quoted_span: str = Field(
        description="A short verbatim quote (one sentence) copied EXACTLY "
        "from the retrieved chunk that supports the answer."
    )

class Answer(BaseModel):
    # This is the schema for the final answer returned by the LLM. It includes the answer text and a list of citations that support the answer.
    answer: str = Field(description="The final answer to the user's question.")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Supporting quotes, each copied verbatim from the context.",
    )

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from parent_retriever import _get_groq, LLM_MODEL  # reuse the singleton + model


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
    """Loose match: collapse whitespace + lowercase so trivial formatting
    differences don't fail an otherwise-real quote."""
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