"""Centralised configuration loaded from environment variables / .env file.

Production (Render) injects vars via the dashboard; local dev reads .env.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Required secrets ────────────────────────────────────────────────
    groq_api_key: str

    # ── Qdrant ──────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None  # required for Qdrant Cloud

    # ── Models ──────────────────────────────────────────────────────────
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    llm_model: str = "llama-3.3-70b-versatile"

    # ── Retrieval knobs ────────────────────────────────────────────────
    collection: str = "SDN"
    top_k: int = 5
    candidates: int = 25
    n_variants: int = 3


settings = Settings()  # type: ignore[call-arg]
