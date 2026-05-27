from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

client = QdrantClient("http://localhost:6333")

client.recreate_collection(
    collection_name="SDN",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

with open("Section_B_SDN.md","r", encoding="utf-8") as f:
    text = f.read()

chunk_size = 200

chunks =[
    text[i:i+chunk_size] for i in range(0, len(text), chunk_size)
]

vectors = model.encode(chunks)

# PointStruct imports the structure/template Qdrant uses for storing data.

points = []

for i, (v, t) in enumerate(zip(vectors, chunks)):
    points.append(PointStruct(id=i, vector=v.tolist(), payload={"text": t}))

client.upsert(
    collection_name="SDN",
    points=points
)

query = "Data Plane and Control Plane in SDN"

qvec = model.encode(query).tolist()

hits = client.query_points(
    collection_name="SDN", query=qvec, limit=3, with_payload=True
).points

for h in hits:
    print(f"{h.score:.4f} ----->> {h.payload['text']}")
