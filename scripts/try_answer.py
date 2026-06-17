import sys
sys.path.insert(0, "scripts")
from parent_retriever import retrieve_baseline
from answer_schema import generate_answer, verify_citations

q = "What are the main security challenges in SDN?"
chunks = retrieve_baseline(q, 5)

ans = generate_answer(q, chunks)
print("ANSWER:", ans.answer, "\n")
print("RAW citations     :", len(ans.citations))
for c in ans.citations:
    print("  -", c.source, "|", c.quoted_span[:70])

verified = verify_citations(ans, chunks)
print("\nVERIFIED citations:", len(verified.citations))
for c in verified.citations:
    print("  -", c.source, "|", c.quoted_span[:70])
print(f"\ndropped {len(ans.citations) - len(verified.citations)} hallucinated citation(s)")