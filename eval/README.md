# RAG Evaluation Harness (Week 4)

A production-style evaluation harness for the SDN RAG pipeline. It scores the
system on a golden Q&A set using [Ragas](https://docs.ragas.io), gates pull
requests in CI, and tracks quality over time in a Streamlit dashboard.

## What gets measured

Four [Ragas](https://docs.ragas.io) metrics (all use an LLM judge):

| Metric | Question it answers |
|--------|--------------------|
| **faithfulness** | Is the answer grounded in the retrieved chunks (no hallucination)? |
| **answer_relevancy** | Does the answer actually address the question? |
| **context_precision** | Are the retrieved chunks relevant (low noise)? |
| **context_recall** | Did retrieval find the chunks needed to answer? |

The judge is Groq `llama-3.1-8b-instant` via its OpenAI-compatible endpoint
(free). Embeddings for `answer_relevancy` use the local FastEmbed
`bge-small-en-v1.5` model — the same one used at index time.

## Files

| File | Role |
|------|------|
| `golden_set.json` | 50 hand-labeled SDN Q&A pairs (the ground truth) |
| `harness.py` | **Single source of truth** — RAG calls + Ragas scoring |
| `run_ragas.py` | CLI: runs the full eval, saves `last_run.json`, appends history |
| `append_history.py` | Appends one run's means + per-pair scores to `history.json` |
| `save_baseline.py` | Promotes `last_run.json` means to `baseline.json` |
| `upload_langsmith.py` | Uploads the golden set to LangSmith as a dataset |
| `last_run.json` | Per-row scores from the most recent run |
| `baseline.json` | The reference scores regression tests compare against |
| `history.json` | Rolling log of every run, used by the dashboard |

## How the "garbage scores" bug was fixed

The old runner silently swallowed RAG failures and inserted empty-context
placeholder rows, which made Ragas report `null` / `0.0` for everything.
`harness.py` now **raises loudly** if the RAG endpoint errors or returns no
contexts (`strict=True`), so a broken server fails the run instead of
corrupting the metrics. Metric column names are also normalised to a stable
set: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.

## Running it

Start the RAG server first (in another terminal):

```bash
uv run uvicorn app.main:app --port 8000
```

Then run the eval:

```bash
# full 50-pair run
uv run python eval/run_ragas.py

# quick smoke run (first 5 pairs)
EVAL_SUBSET=5 uv run python eval/run_ragas.py
```

Create / refresh the regression baseline after a good run:

```bash
uv run python eval/save_baseline.py
```

## Pytest gate

```bash
uv run pytest tests/ -v
```

- `test_faithfulness.py`, `test_answer_relevance.py`, `test_context_precision.py`
  assert each mean metric clears its threshold in `tests/thresholds.py`.
- `test_regression.py` fails if any metric dropped more than
  `MAX_REGRESSION_DROP` (0.03) versus `baseline.json` (skips if no baseline yet).

## CI

`.github/workflows/eval.yml` runs on every PR to `main`: it spins up a Qdrant
service container, ingests the corpus, starts the server, runs the pytest gate
on a CI subset (`EVAL_SUBSET=8`), and posts the results as a PR comment.
Requires the `GROQ_API_KEY` repository secret.

## Dashboard

```bash
uv run streamlit run dashboard/app.py
```

Shows metric trends over time, the latest run's pass/fail vs thresholds, and
the worst-scoring pairs to investigate.

## Notes on quotas

The answer-generation model (`llama-3.3-70b-versatile`) has a 100K tokens/day
free-tier limit on Groq. A full 50-pair run uses it twice per question (query
expansion + generation). If you hit the daily cap, either wait for the reset or
temporarily run the server with the higher-limit model:

```bash
LLM_MODEL=llama-3.1-8b-instant uv run uvicorn app.main:app --port 8000
```
