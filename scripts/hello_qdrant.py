from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

# 1. Connect
client = QdrantClient("http://localhost:6333")

# 2. Create collection (delete if exists, for dev)
client.recreate_collection(
    collection_name="hello",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# 3. Embed 5 sentences
model = SentenceTransformer("BAAI/bge-small-en-v1.5")
texts = [
    "The capital of Nepal is Kathmandu.",
    "Mount Everest is the highest mountain in the world.",
    "Python is a popular programming language.",
    "Llamas are South American camelids.",
    "Kathmandu is in the Bagmati province.",
]
vectors = model.encode(texts)

# 4. Upload
client.upsert(
    collection_name="hello",
    points=[
        PointStruct(id=i, vector=v.tolist(), payload={"text": t})
        for i, (v, t) in enumerate(zip(vectors, texts))
    ],
)

# 5. Search
query = "What city is Nepal's capital?"
qvec = model.encode(query).tolist()
hits = client.query_points(
    collection_name="hello", query=qvec, limit=3, with_payload=True
).points

for h in hits:
    print(f"{h.score:.4f}  {h.payload['text']}")