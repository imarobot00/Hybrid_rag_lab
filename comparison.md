# Retriever comparison

Corpus: `notes_all` (6 sections). Golden set: 50 SDN questions.
Metric: source-level recall (a hit = the question's source document
appears in the top-k).

> **Note:** `recall@5` saturates at 1.00 on this corpus — the correct
> source is always somewhere in the top 5 — so it cannot discriminate
> retrievers. **`recall@1` is the metric with real signal** and is the
> one to compare. Latency is wall-clock per query (local Qdrant + Groq).

| retriever | recall@1 | recall@5 | latency (avg) | extra_llm_calls |
| --- | --- | --- | --- | --- |
| vanilla          | 0.88 | 1.00 | 10ms | 0 |
| parent_doc       | 0.88 | 1.00 | 13ms | 0 |
| multi_query      | 0.90 | 1.00 | 1286ms | 1 |
| hyde             | 0.92 | 1.00 | 2642ms | 1 |
| multi_query+hyde | 0.90 | 1.00 | 5226ms | 2 |
