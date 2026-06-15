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
from collections import defaultdict
from pathlib import Path

# Make the sibling `scripts/` package importable so we reuse the exact same
# retrieval code the rest of the project uses (no duplicated query logic).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parent_retriever import retrieve_baseline, retrieve_with_parents  # noqa: E402

EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden_set.json"
RESULTS_PATH = EVAL_DIR / "recall_results.json"

RETRIEVERS = {
    "baseline": retrieve_baseline,
    "parent": retrieve_with_parents,
}

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

    for i, ex in enumerate(golden):
        want = ex["source_document"]
        results = retriever(ex["question"], max_k)
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
        flag = "".join("H" if row_hit[k] else "." for k in KS)
        print(f"  [{i + 1:>2}/{len(golden)}] @{KS}={flag} {ex['id']}")

    total = len(golden)
    report = {
        "retriever": retriever_name,
        "total": total,
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
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retriever", choices=list(RETRIEVERS), default="baseline"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"RECALL EVALUATION — retriever='{args.retriever}'")
    print("=" * 60)

    report = evaluate(args.retriever)

    print("\n" + "=" * 60)
    for k in KS:
        print(f"  recall@{k} = {report['recall'][f'@{k}']:.4f} "
              f"({report['hits'][f'@{k}']}/{report['total']})")
    print("=" * 60)
    print("  by question type (recall@1 / @3 / @5):")
    for t, d in report["by_qtype"].items():
        cells = " / ".join(f"{d[f'@{k}']:.2f}" for k in KS)
        print(f"    {t:<12} {cells}   (n={d['total']})")

    # Merge into a results file keyed by retriever so baseline + parent
    # numbers live side by side for easy comparison.
    existing = {}
    if RESULTS_PATH.exists():
        existing = json.loads(RESULTS_PATH.read_text())
    existing[args.retriever] = report
    RESULTS_PATH.write_text(json.dumps(existing, indent=2))
    print(f"\nSaved -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
