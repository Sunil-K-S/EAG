import requests
import json
import numpy as np

def get_ollama_embedding(text, model="nomic-embed-text"):
    """
    Get embeddings from Ollama using the specified model
    """
    url = "http://localhost:11434/api/embeddings"
    data = {
        "model": model,
        "prompt": text
    }
    
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return np.array(response.json()['embedding'], dtype=np.float32)
    else:
        raise Exception(f"Error getting embeddings: {response.text}")

# Example usage
texts = [
    "How does AlphaFold work?",
    "What is machine learning?",
    "Explain quantum computing"
]

print("Generating embeddings using Ollama (nomic-embed-text)...")
for text in texts:
    print(f"\nText: {text}")
    embedding = get_ollama_embedding(text)
    print(f"🔢 Vector length: {len(embedding)}")
    print(f"📈 First 5 values: {embedding[:5]}")
    
    # Calculate similarity with other texts
    if text != texts[0]:
        base_embedding = get_ollama_embedding(texts[0])
        similarity = np.dot(embedding, base_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(base_embedding))
        print(f"🤝 Similarity with first text: {similarity:.4f}")