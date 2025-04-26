import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import google.generativeai as genai
import numpy as np
import faiss
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Helper: Get Gemini embedding for a text
def get_embedding(text: str) -> np.ndarray:
    result = genai.embed_content(
        model="models/gemini-embedding-exp-03-07",
        content=text,
        task_type="CLUSTERING"
    )
    return np.array(result['embedding'], dtype=np.float32)

# Step 1: Sentences to index
print("\n📚 Original Sentences:")
sentences = [
    "The early bird catches the worm.",
    "A stitch in time saves nine.",
    "Better late than never.",
    "Birds of a feather flock together."
]
for i, s in enumerate(sentences):
    print(f"{i+1}. {s}")

# Step 2: Get embeddings and create FAISS indices with different distance metrics
print("\n🔍 Generating embeddings for each sentence...")
embeddings = [get_embedding(s) for s in sentences]
dimension = len(embeddings[0])
print(f"Embedding dimension: {dimension}")

# Create different FAISS indices
print("\n🏗️ Creating FAISS indices with different distance metrics...")
indices = {
    "L2 (Euclidean)": faiss.IndexFlatL2(dimension),        # Euclidean distance
    "Inner Product": faiss.IndexFlatIP(dimension),         # Inner product (cosine similarity when vectors are normalized)
}

# Add embeddings to all indices
for name, index in indices.items():
    index.add(np.stack(embeddings))
    print(f"Created {name} index")

# Step 3: Query embedding
query = "People with similar traits stick together."
print(f"\n❓ Query: \"{query}\"")
print("Generating embedding for query...")
query_embedding = get_embedding(query).reshape(1, -1)

# Step 4: Search all indices and compare results
print("\n🔎 Searching with different distance metrics...")
for name, index in indices.items():
    print(f"\n📊 Results using {name}:")
    D, I = index.search(query_embedding, k=len(sentences))  # Get all distances
    
    # For Inner Product, higher values mean more similar
    # For L2, lower values mean more similar
    is_distance = name != "Inner Product"
    
    print("Distances to all sentences (sorted by similarity):")
    sorted_indices = np.argsort(D[0]) if is_distance else np.argsort(-D[0])
    for i, idx in enumerate(sorted_indices):
        dist = D[0][idx]
        if is_distance:
            print(f"{i+1}. Distance: {dist:.4f} - \"{sentences[I[0][idx]]}\"")
        else:
            print(f"{i+1}. Similarity: {dist:.4f} - \"{sentences[I[0][idx]]}\"")
    
    print(f"Most similar sentence: \"{sentences[I[0][0]]}\"")