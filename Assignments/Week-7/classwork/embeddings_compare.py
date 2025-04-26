import google.generativeai as genai
import numpy as np
import os
from dotenv import load_dotenv
from scipy.spatial.distance import cosine

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text, model="models/embedding-001"):
    res = genai.embed_content(
        model=model,
        content=text,
        task_type="retrieval_document"
    )
    return np.array(res['embedding'], dtype=np.float32)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# 🎯 Phrases to compare
sentences = [
    "How does AlphaFold work?",
    "How do proteins fold?",
    "What is the capital of France?",
    "Explain how neural networks learn."
]

models = ["models/embedding-001", "models/text-embedding-004", "models/gemini-embedding-exp-03-07"]

for model in models:
    print(f"\nUsing model: {model}")
    embeddings = [get_embedding(s, model) for s in sentences]
    
    # Compare all pairs
    print("🔍 Semantic Similarity Matrix:\n")
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            print(f"\"{sentences[i]}\" ↔ \"{sentences[j]}\" → similarity = {sim:.3f}")
