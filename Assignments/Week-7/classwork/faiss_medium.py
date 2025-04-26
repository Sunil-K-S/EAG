from google import genai
from google.genai import types
import faiss
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# 🔐 Gemini Setup
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text: str) -> np.ndarray:
    result = client.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents=text,
        config=types.EmbedContentConfig(task_type="CLUSTERING")
    )
    return np.array(result.embeddings[0].values, dtype=np.float32)

# 🎭 Corpus of jokes with metadata
jokes = [
    {"id": 1, "category": "animals", "text": "Why don’t cows have any money? Because farmers milk them dry."},
    {"id": 2, "category": "tech", "text": "Why do programmers prefer dark mode? Because light attracts bugs."},
    {"id": 3, "category": "school", "text": "Why did the student eat his homework? Because the teacher said it was a piece of cake."},
    {"id": 4, "category": "classic", "text": "I told my wife she was drawing her eyebrows too high. She looked surprised."},
    {"id": 5, "category": "tech", "text": "How do you comfort a JavaScript bug? You console it."}
]

# ✨ Create FAISS index
embeddings = [get_embedding(j["text"]) for j in jokes]
dimension = len(embeddings[0])
index = faiss.IndexFlatL2(dimension)
index.add(np.stack(embeddings))

# 🧠 Store joke metadata by index
metadata_lookup = {i: jokes[i] for i in range(len(jokes))}

# 🧐 Query
query = "Something about software engineers and debugging."
query_vector = get_embedding(query).reshape(1, -1)

# 🔍 Top-3 search
D, I = index.search(query_vector, k=3)

# 🎉 Results
print(f"Query: {query}")
print("\nTop Joke Matches:")
for rank, idx in enumerate(I[0]):
    joke = metadata_lookup[idx]
    print(f"\n#{rank + 1}:")
    print(f"  ID: {joke['id']}")
    print(f"  Category: {joke['category']}")
    print(f"  Joke: {joke['text']}")
