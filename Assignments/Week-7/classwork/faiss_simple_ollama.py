import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import faiss
import numpy as np
import requests
import json

# Helper: Get Ollama embedding for a text
def get_embedding(text: str) -> np.ndarray:
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "nomic-embed-text",
            "prompt": text
        }
    )
    response.raise_for_status()
    return np.array(response.json()["embedding"], dtype=np.float32)

# Step 1: Sentences to index
sentences = [
    "The early bird catches the worm.",
    "A stitch in time saves nine.",
    "Better late than never.",
    "Birds of a feather flock together."
]

# Step 2: Get embeddings and create FAISS index
embeddings = [get_embedding(s) for s in sentences]
dimension = len(embeddings[0])  # Should be 768 for nomic-embed-text
index = faiss.IndexFlatL2(dimension)
index.add(np.stack(embeddings))

# Step 3: Query embedding
query = "People with similar traits stick together."
query_embedding = get_embedding(query).reshape(1, -1)

# Step 4: Search FAISS
D, I = index.search(query_embedding, k=1)
print(f"Closest match to: \"{query}\"")
print(f">>> {sentences[I[0][0]]}")
