from google import genai
from google.genai import types
import faiss
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# Load API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# Helper: Get Gemini embedding for a text
def get_embedding(text: str) -> np.ndarray:
    result = client.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents=text,
        config=types.EmbedContentConfig(task_type="CLUSTERING") #https://ai.google.dev/gemini-api/docs/embeddings
    )
    return np.array(result.embeddings[0].values, dtype=np.float32)

# Step 1: Sentences to index
sentences = [
    "The early bird catches the worm.",
    "A stitch in time saves nine.",
    "Better late than never.",
    "Birds of a feather flock together."
]

# Step 2: Get embeddings and create FAISS index
embeddings = [get_embedding(s) for s in sentences]
dimension = len(embeddings[0])
index = faiss.IndexFlatL2(dimension)
index.add(np.stack(embeddings))

# Step 3: Query embedding
query = "People with similar traits stick together."
query_embedding = get_embedding(query).reshape(1, -1)

# Step 4: Search FAISS
D, I = index.search(query_embedding, k=1)
print(f"Closest match to: \"{query}\"")
print(f">>> {sentences[I[0][0]]}")