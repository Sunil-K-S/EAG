import google.generativeai as genai
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# List available models with detailed information
print("Listing available models with details...")
for m in genai.list_models():
    print(f"\nModel Details:")
    print(f"Name: {m.name}")
    print(f"Display Name: {m.display_name}")
    print(f"Description: {m.description}")
    print(f"Supported Generation Methods: {m.supported_generation_methods}")
    print(f"Input Token Limit: {m.input_token_limit}")
    print(f"Output Token Limit: {m.output_token_limit}")
    print("-" * 80)

# Focus on embedding models
print("\nEmbedding Models Details:")
embedding_models = [m for m in genai.list_models() if "embedding" in m.name.lower()]
for m in embedding_models:
    print(f"\nEmbedding Model: {m.name}")
    print(f"Display Name: {m.display_name}")
    print(f"Description: {m.description}")
    print(f"Supported Generation Methods: {m.supported_generation_methods}")
    print("-" * 80)

sentence = "How does AlphaFold work?"

# Try different embedding models
for model_name in ["models/embedding-001", "models/text-embedding-004", "models/gemini-embedding-exp-03-07"]:
    print(f"\nGenerating embedding using {model_name}:")
    response = genai.embed_content(
        model=model_name,
        content=sentence,
        task_type="retrieval_document"
    )

    embedding_vector = np.array(response['embedding'], dtype=np.float32)
    print(f"🔢 Vector length: {len(embedding_vector)}")
    print(f"📈 First 5 values: {embedding_vector[:5]}")
    # print(f"📊 Vector statistics:")
    # print(f"   Min: {np.min(embedding_vector):.4f}")
    # print(f"   Max: {np.max(embedding_vector):.4f}")
    # print(f"   Mean: {np.mean(embedding_vector):.4f}")
    # print(f"   Std: {np.std(embedding_vector):.4f}")
