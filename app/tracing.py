"""LangSmith tracing shim.

LangSmith records a structured tree (a "trace") of every step your RAG
pipeline takes — the query expansion, each retrieval, the rerank, and the
final LLM call — so you can click into a single bad answer in the LangSmith UI
and see exactly which stage produced it.

This module exposes a `traceable` decorator that:
    * uses the real LangSmith decorator when langsmith is installed AND
      LANGSMITH_TRACING=true is set in the environment;
    * otherwise becomes a harmless no-op, so the app runs fine without
      LangSmith configured.

To turn tracing ON, put these in your .env (and as GitHub Secrets for CI):
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=ls__xxxxxxxx
    LANGSMITH_PROJECT=rag-lab-week4
"""
from __future__ import annotations

import os
from typing import Any, Callable

_ENABLED = os.getenv("LANGSMITH_TRACING", "").lower() == "true"

if _ENABLED:
    try:
        from langsmith import traceable as _ls_traceable  # type: ignore

        def traceable(*args: Any, **kwargs: Any) -> Callable:
            """Pass through to the real LangSmith decorator."""
            return _ls_traceable(*args, **kwargs)

    except ImportError:  # langsmith not installed — degrade gracefully
        _ENABLED = False

if not _ENABLED:

    def traceable(*_args: Any, **_kwargs: Any) -> Callable:
        """No-op decorator used when tracing is disabled.

        Supports both @traceable and @traceable(run_type=..., name=...) forms.
        """
        # Form 1: used bare as @traceable on a function.
        if len(_args) == 1 and callable(_args[0]) and not _kwargs:
            return _args[0]

        # Form 2: used with arguments as @traceable(...).
        def decorator(func: Callable) -> Callable:
            return func

        return decorator
