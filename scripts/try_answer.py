import sys
sys.path.insert(0, "scripts")
from answer_schema import answer_question

q = "What are the main security challenges in SDN?"
parsed, chunks, raw_answer, verified_answer = answer_question(q, 5)

print("INPUT   :", q)
print("REWRITE :", parsed["rewritten_query"])
print("FILTERS :", parsed["filters"])
print("SOURCES :", [chunk["source"] for chunk in chunks])

print("\nANSWER:", raw_answer.answer, "\n")
print("RAW citations     :", len(raw_answer.citations))
for citation in raw_answer.citations:
    print("  -", citation.source, "|", citation.quoted_span[:70])

print("\nVERIFIED citations:", len(verified_answer.citations))
for citation in verified_answer.citations:
    print("  -", citation.source, "|", citation.quoted_span[:70])
print(f"\ndropped {len(raw_answer.citations) - len(verified_answer.citations)} hallucinated citation(s)")