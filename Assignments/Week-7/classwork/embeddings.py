from google import genai
from google.genai import types
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

sentence = "How does AlphaFold work?"

response = client.models.embed_content(
    model="gemini-embedding-exp-03-07",
    contents=sentence,
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
)

embedding_vector = np.array(response.embeddings[0].values, dtype=np.float32)

print(f"🔢 Vector length: {len(embedding_vector)}")
print(f"📈 First 5 values: {embedding_vector[:5]}")
