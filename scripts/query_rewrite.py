"""Query rewriting — clean up a raw user question before it hits the retriever.

A query rewriter takes a vague / pronoun-heavy question and rewrites it into a
sharper search query (e.g. "how does it work?" -> "how does the OpenFlow
controller process a packet with no matching flow rule?"). It helps most on
ambiguous queries and should NEVER hurt queries that already retrieve well.

================================================================================
TODAY'S STRESS TEST — 10 golden_set.json IDs
================================================================================
We measure the rewriter against a fixed 10-query set, in two groups.

GROUP A — 5 HARD queries (reasoning/synthesis, keyword-rich).
  These already retrieve correctly (recall@5 = 1.00 on 2026-06-15). They are
  the GUARDRAIL: rewriting must not make these worse.
    sdn-004  Why is the Controller Placement Problem (CPP) NP-hard?
    sdn-007  How does a Genetic Algorithm solve the Multi-Controller Placement Problem?
    sdn-013  Key differences between P4_14 and P4_16?
    sdn-018  What makes ISP/Telco SDN deployment different from data center?
    sdn-032  How does K-Center differ from K-Median for controller placement?

GROUP B — 5 AMBIGUOUS queries (short / vague / open-ended referents).
  Vaguest questions in the set — where rewriting should HELP.
    sdn-006  What are the main scalability challenges in SDN control planes?
    sdn-021  What is the core idea that distinguishes SDN from a traditional network?
    sdn-022  Which analogy is used to describe SDN versus a traditional network?
    sdn-030  What analogy is used to explain the Controller Placement Problem?
    sdn-040  What are some emerging research directions in SDN?

NOTE: golden_set.json contains no truly short / pronoun-heavy queries (they are
all well-formed exam questions). Group B is the closest approximation. For a
stronger ambiguity stress test, hand-write *degraded* versions of these (e.g.
"how does it work?", "what's the difference?") and add them here later.
================================================================================
"""
from __future__ import annotations

STRESS_TEST_IDS = [
    # Group A — hard (guardrail)
    "sdn-004",
    "sdn-007",
    "sdn-013",
    "sdn-018",
    "sdn-032",
    # Group B — ambiguous (opportunity)
    "sdn-006",
    "sdn-021",
    "sdn-022",
    "sdn-030",
    "sdn-040",
]
