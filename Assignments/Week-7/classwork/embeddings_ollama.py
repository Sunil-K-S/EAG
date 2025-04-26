import numpy as np
import requests
import json

# Example sentence to embed
sentence = "How does AlphaFold work?"

# Get embedding from Ollama
response = requests.post(
    "http://localhost:11434/api/embeddings",
    json={
        "model": "nomic-embed-text",
        "prompt": sentence
    }
)
response.raise_for_status()

# Convert to numpy array
embedding_vector = np.array(response.json()["embedding"], dtype=np.float32)

print(f"🔢 Vector length: {len(embedding_vector)}")  # Should be 768 for nomic-embed-text
print(f"📈 First 5 values: {embedding_vector[:5]}")
