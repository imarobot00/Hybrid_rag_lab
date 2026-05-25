from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-small-en-v1.5")
vec = model.encode("The capital of Nepal is Kathmandu.")
print(f"dim={len(vec)}, first 5={vec[:5]}")