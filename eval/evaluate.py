"""recall@5 — the single number every retrieval upgrade is measured against.

Definition (source-level recall@5)
----------------------------------
The golden set is 50 SDN questions, every one of which should be answered from
`Section_B_SDN.md`. Now that all SIX sections live in Qdrant, the retriever has
to pick SDN content out of five neighbouring topics (two of which —
`Section_D_SDN_5G.md` and `Section_F_SDN_Security.md` — overlap heavily with
core SDN). So we score:

    A question is a HIT if at least one of the top-5 retrieved results comes
    from the question's `source_document`.  recall@5 = hits / total.

We deliberately use *source-level* matching: the golden `expected_chunk` ids
(e.g. `Section_B_SDN.md#chunk_q9`) are hand-written question ids and do NOT map
onto ingestion chunk ids, so exact-chunk matching is impossible. Source-level
recall is the honest, deterministic, LLM-free signal — and with SDN-5G/SDN-Sec
in the corpus it is genuinely discriminating, not saturated at 1.0.

Usage (from project root, Qdrant running):
    uv run python eval/evaluate.py --retriever baseline   # over notes_all
    uv run python eval/evaluate.py --retriever parent      # parent-doc retriever
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Make the sibling `scripts/` package importable so we reuse the exact same
# retrieval code the rest of the project uses (no duplicated query logic).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parent_retriever import (  # noqa: E402
    retrieve_baseline,
    retrieve_with_parents,
    retrieve_multi_query,
    retrieve_hyde,
    retrieve_multi_query_hyde,
)

EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden_set.json"
RESULTS_PATH = EVAL_DIR / "recall_results.json"
COMPARISON_PATH = ROOT / "comparison.md"
FAILURES_PATH = ROOT / "docs" / "failures.md"

# Canonical names match the Pomodoro spec; baseline/parent kept as aliases so
# older commands still work.
RETRIEVERS = {
    "vanilla": retrieve_baseline,
    "parent_doc": retrieve_with_parents,
    "multi_query": retrieve_multi_query,
    "hyde": retrieve_hyde,
    "multi_query+hyde": retrieve_multi_query_hyde,
    # aliases
    "baseline": retrieve_baseline,
    "parent": retrieve_with_parents,
}

# How many EXTRA LLM calls each retriever makes per query (for the cost column).
EXTRA_LLM_CALLS = {
    "vanilla": 0,
    "parent_doc": 0,
    "multi_query": 1,
    "hyde": 1,
    "multi_query+hyde": 2,
}

# The five retrievers compared in the sweep, in report order.
SWEEP = ["vanilla", "parent_doc", "multi_query", "hyde", "multi_query+hyde"]

KS = (1, 3, 5)  # report recall at several depths; recall@5 is the headline.


def load_golden() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text())


def evaluate(retriever_name: str, max_k: int = 5) -> dict:
    """Retrieve top-`max_k` once per question, then score recall at each k in KS.

    Source-level recall@5 saturates at 1.0 on this corpus (SDN is distinctive
    enough that a relevant chunk is always somewhere in the top 5), so the
    shallower recall@1 / recall@3 are what actually carry signal between
    retriever versions.
    """
    retriever = RETRIEVERS[retriever_name]
    golden = load_golden()

    hits = {k: 0 for k in KS}
    per_type: dict[str, dict] = defaultdict(
        lambda: {"total": 0, **{k: 0 for k in KS}}
    )
    misses: list[dict] = []  # questions missed even at the deepest k
    per_query: list[dict] = []  # per-question detail (for A/B failure analysis)
    latencies: list[float] = []

    for i, ex in enumerate(golden):
        want = ex["source_document"]
        t0 = time.perf_counter()
        results = retriever(ex["question"], max_k)
        latencies.append((time.perf_counter() - t0) * 1000.0)  # ms
        sources = [r["source"] for r in results[:max_k]]

        qtype = ex.get("qtype", "unknown")
        per_type[qtype]["total"] += 1
        row_hit = {k: (want in sources[:k]) for k in KS}
        for k in KS:
            if row_hit[k]:
                hits[k] += 1
                per_type[qtype][k] += 1
        if not row_hit[max(KS)]:
            misses.append(
                {"id": ex["id"], "question": ex["question"], "got": sources}
            )
        per_query.append(
            {
                "id": ex["id"],
                "question": ex["question"],
                "want": want,
                "hit@1": row_hit[1],
                "hit@5": row_hit[5],
                "got": sources,
            }
        )
        flag = "".join("H" if row_hit[k] else "." for k in KS)
        print(f"  [{i + 1:>2}/{len(golden)}] @{KS}={flag} {ex['id']}")

    total = len(golden)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    report = {
        "retriever": retriever_name,
        "total": total,
        "avg_latency_ms": round(avg_latency, 1),
        "extra_llm_calls": EXTRA_LLM_CALLS.get(retriever_name, 0),
        "recall": {f"@{k}": round(hits[k] / total, 4) if total else 0.0 for k in KS},
        "hits": {f"@{k}": hits[k] for k in KS},
        "recall_at_5": round(hits[5] / total, 4) if total else 0.0,
        "by_qtype": {
            t: {
                "total": d["total"],
                **{f"@{k}": round(d[k] / d["total"], 4) if d["total"] else 0.0 for k in KS},
            }
            for t, d in sorted(per_type.items())
        },
        "misses": misses,
        "per_query": per_query,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
def _print_report(report: dict) -> None:
    print("\n" + "=" * 60)
    for k in KS:
        print(f"  recall@{k} = {report['recall'][f'@{k}']:.4f} "
              f"({report['hits'][f'@{k}']}/{report['total']})")
    print(f"  avg latency = {report['avg_latency_ms']:.1f} ms   "
          f"extra LLM calls = {report['extra_llm_calls']}")
    print("=" * 60)
    print("  by question type (recall@1 / @3 / @5):")
    for t, d in report["by_qtype"].items():
        cells = " / ".join(f"{d[f'@{k}']:.2f}" for k in KS)
        print(f"    {t:<12} {cells}   (n={d['total']})")


def _save_result(report: dict) -> None:
    existing = {}
    if RESULTS_PATH.exists():
        existing = json.loads(RESULTS_PATH.read_text())
    existing[report["retriever"]] = report
    RESULTS_PATH.write_text(json.dumps(existing, indent=2))


def write_comparison(reports: dict[str, dict]) -> None:
    """Write the recall/latency/cost table to comparison.md."""
    lines = [
        "# Retriever comparison",
        "",
        f"Corpus: `notes_all` (6 sections). Golden set: {next(iter(reports.values()))['total']} SDN questions.",
        "Metric: source-level recall (a hit = the question's source document",
        "appears in the top-k).",
        "",
        "> **Note:** `recall@5` saturates at 1.00 on this corpus — the correct",
        "> source is always somewhere in the top 5 — so it cannot discriminate",
        "> retrievers. **`recall@1` is the metric with real signal** and is the",
        "> one to compare. Latency is wall-clock per query (local Qdrant + Groq).",
        "",
        "| retriever | recall@1 | recall@5 | latency (avg) | extra_llm_calls |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in SWEEP:
        r = reports[name]
        lines.append(
            f"| {name:<16} | {r['recall']['@1']:.2f} | {r['recall']['@5']:.2f} "
            f"| {r['avg_latency_ms']:.0f}ms | {r['extra_llm_calls']} |"
        )
    lines.append("")
    COMPARISON_PATH.write_text("\n".join(lines))
    print(f"\nWrote {COMPARISON_PATH}")


def write_failures(reports: dict[str, dict]) -> None:
    """Find queries where multi_query did WORSE than vanilla at recall@1 and
    document them in docs/failures.md (paraphrase drift is the usual culprit)."""
    vanilla = {q["id"]: q for q in reports["vanilla"]["per_query"]}
    mq = {q["id"]: q for q in reports["multi_query"]["per_query"]}

    regressions = [
        mq[qid]
        for qid in mq
        if vanilla[qid]["hit@1"] and not mq[qid]["hit@1"]
    ]

    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Retriever failure cases",
        "",
        "## Multi-query made retrieval worse",
        "",
        "Queries where **vanilla** placed the correct source at rank 1 but",
        "**multi_query** did not (recall@1 regression). Cause: LLM paraphrases",
        "drift toward neighbouring topics, pulling off-source chunks into the",
        "pool and pushing the correct chunk out of the #1 slot.",
        "",
    ]
    if not regressions:
        lines += [
            "_No recall@1 regression observed in this run._ Multi-query did not",
            "demote any vanilla rank-1 hit. (With recall saturated this can",
            "happen; re-run or inspect recall@1 on a harder/ambiguous query set",
            "to surface drift.)",
        ]
    else:
        for q in regressions:
            lines += [
                f"### `{q['id']}` — {q['question']}",
                f"- Wanted source: `{q['want']}`",
                f"- multi_query top-5 sources: `{q['got']}`",
                f"- vanilla rank-1 was correct; multi_query rank-1 was `{q['got'][0] if q['got'] else '?'}`",
                "",
            ]
    FAILURES_PATH.write_text("\n".join(lines))
    print(f"Wrote {FAILURES_PATH} ({len(regressions)} regression(s))")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retriever",
        choices=["vanilla", "parent_doc", "multi_query", "hyde", "multi_query+hyde",
                 "baseline", "parent"],
        default="vanilla",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run all five retrievers and write comparison.md + docs/failures.md.",
    )
    args = parser.parse_args()

    if args.compare:
        reports: dict[str, dict] = {}
        for name in SWEEP:
            print("=" * 60)
            print(f"RECALL EVALUATION — retriever='{name}'")
            print("=" * 60)
            rep = evaluate(name)
            _print_report(rep)
            _save_result(rep)
            reports[name] = rep
        write_comparison(reports)
        write_failures(reports)
        return

    print("=" * 60)
    print(f"RECALL EVALUATION — retriever='{args.retriever}'")
    print("=" * 60)
    report = evaluate(args.retriever)
    _print_report(report)
    _save_result(report)
    print(f"\nSaved -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
