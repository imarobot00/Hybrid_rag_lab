# Retriever failure cases

## Multi-query made retrieval worse

Queries where **vanilla** placed the correct source at rank 1 but
**multi_query** did not (recall@1 regression). Cause: LLM paraphrases
drift toward neighbouring topics, pulling off-source chunks into the
pool and pushing the correct chunk out of the #1 slot.

### `sdn-031` — What are the five key performance metrics for SDN controllers?
- Wanted source: `Section_B_SDN.md`
- multi_query top-5 sources: `['Section_D_SDN_5G.md', 'Section_B_SDN.md', 'Section_B_SDN.md', 'Section_B_SDN.md', 'Section_B_SDN.md']`
- vanilla rank-1 was correct; multi_query rank-1 was `Section_D_SDN_5G.md`
