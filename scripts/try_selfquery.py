import sys
sys.path.insert(0, "scripts")
from parent_retriever import self_query, filters_to_qdrant, retrieve_baseline

tests = [
    "what does my SDN section say about security",
    "how does IoT handle wireless sensor networks",
    "what are the main security challenges",        # ambiguous, no section word
]

for q in tests:
    parsed = self_query(q)
    qf = filters_to_qdrant(parsed["filters"])
    print("\nINPUT   :", q)
    print("REWRITE :", parsed["rewritten_query"])
    print("FILTERS :", parsed["filters"])
    hits = retrieve_baseline(parsed["rewritten_query"], 5, qf)
    print("SOURCES :", [h["source"] for h in hits])