"""FastAPI entrypoint. Run locally with:

    uv run uvicorn app.main:app --reload

Open http://localhost:8000/docs for the interactive Swagger UI.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import rag
from .settings import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="RAG Lab",
    version="0.1.0",
    description="Hybrid + multi-query + rerank RAG over the SDN study notes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class Source(BaseModel):
    chunk_id: int
    source: str
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    variants: list[str]
    sources: list[Source]
    pool_size: int


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "collection": settings.collection,
        "qdrant": settings.qdrant_url,
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> dict:
    try:
        return rag.answer(req.question)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
