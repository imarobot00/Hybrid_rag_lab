import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

resp = client.models.embed_content(
    model="gemini-embedding-001",
    contents=["The capital of Nepal is Kathmandu."],
)

vec = resp.embeddings[0].values
print(f"dim={len(vec)}, first 5={vec[:5]}")
