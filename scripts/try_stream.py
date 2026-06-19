"""Watch the answer stream in token by token (like ChatGPT typing).

Run:  uv run python scripts/try_stream.py
"""
import sys
import time

sys.path.insert(0, "scripts")
from parent_retriever import filters_to_qdrant, retrieve_baseline, self_query
from answer_schema import generate_answer_stream

q = "What are the main security challenges in SDN?"

# 1. Route + retrieve (same as the non-streaming pipeline)
parsed = self_query(q)
chunks = retrieve_baseline(parsed["rewritten_query"], 5, filters_to_qdrant(parsed["filters"]))

print("FILTERS :", parsed["filters"])
print("SOURCES :", [c["source"] for c in chunks])
print("\nANSWER (streaming):\n")

# 2. Stream the answer — print each token the moment it arrives
full = ""
for token in generate_answer_stream(q, chunks):
    print(token, end="", flush=True)  # flush=True forces it to show immediately
    full += token
    time.sleep(0.01)  # tiny delay just to make the typing effect visible

print("\n\n[done] streamed", len(full), "chars")
