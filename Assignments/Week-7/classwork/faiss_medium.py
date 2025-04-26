import google.generativeai as genai
import faiss
import numpy as np
import os
import time
import random
from datetime import datetime, timedelta
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
from dotenv import load_dotenv

load_dotenv()

# 🔐 Gemini Setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Global variables for quota management
QUOTA_RESET_TIME = None
QUOTA_EXHAUSTED = False

def check_quota_status() -> bool:
    """
    Check if we should wait due to quota exhaustion.
    Returns True if we can proceed, False if we should wait.
    """
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED
    
    if not QUOTA_EXHAUSTED:
        return True
        
    if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
        wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
        print(f"Quota exhausted. Waiting {wait_seconds:.0f} seconds until reset...")
        time.sleep(wait_seconds)
        QUOTA_EXHAUSTED = False
        QUOTA_RESET_TIME = None
        return True
        
    return False

def get_embedding(text: str, max_retries=3) -> np.ndarray:
    """Get embedding for text with retry logic"""
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED
    
    for attempt in range(max_retries):
        try:
            # Check quota status first
            if not check_quota_status():
                continue
                
            result = genai.embed_content(
                model="models/gemini-embedding-exp-03-07",
                content=text,
                task_type="CLUSTERING"
            )
            return np.array(result['embedding'], dtype=np.float32)
        except Exception as e:
            if "quota" in str(e).lower() or "exhausted" in str(e).lower():
                QUOTA_EXHAUSTED = True
                # Set reset time to 1 hour from now (typical quota reset period)
                QUOTA_RESET_TIME = datetime.now() + timedelta(hours=1)
                print("Quota exhausted. Will retry after reset period.")
                return None
                
            if attempt == max_retries - 1:
                raise e
                
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            print(f"Waiting {wait_time:.2f} seconds before retry...")
            time.sleep(wait_time)
            
    raise Exception("Max retries exceeded")

# 🎭 Corpus of jokes with metadata
jokes = [
    {"id": 1, "category": "animals", "text": "Why don't cows have any money? Because farmers milk them dry."},
    {"id": 2, "category": "tech", "text": "Why do programmers prefer dark mode? Because light attracts bugs."},
    {"id": 3, "category": "school", "text": "Why did the student eat his homework? Because the teacher said it was a piece of cake."},
    {"id": 4, "category": "classic", "text": "I told my wife she was drawing her eyebrows too high. She looked surprised."},
    {"id": 5, "category": "tech", "text": "How do you comfort a JavaScript bug? You console it."}
]

print("Generating embeddings for jokes...")
embeddings = []
for joke in jokes:
    print(f"Getting embedding for joke {joke['id']}: {joke['text']}")
    embedding = get_embedding(joke["text"])
    if embedding is None:  # Quota exhausted
        print("Quota exhausted. Stopping embedding generation.")
        break
    embeddings.append(embedding)
    time.sleep(2)  # Conservative delay between calls

if len(embeddings) == len(jokes):
    # ✨ Create FAISS index
    dimension = len(embeddings[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(np.stack(embeddings))

    # 🧠 Store joke metadata by index
    metadata_lookup = {i: jokes[i] for i in range(len(jokes))}

    # 🧐 Query
    query = "Something about software engineers and debugging."
    print(f"\nGenerating embedding for query: {query}")
    query_vector = get_embedding(query)
    
    if query_vector is not None:
        query_vector = query_vector.reshape(1, -1)

        # 🔍 Top-3 search
        D, I = index.search(query_vector, k=3)

        # 🎉 Results
        print(f"\nQuery: {query}")
        print("\nTop Joke Matches:")
        for rank, idx in enumerate(I[0]):
            joke = metadata_lookup[idx]
            print(f"\n#{rank + 1}:")
            print(f"  ID: {joke['id']}")
            print(f"  Category: {joke['category']}")
            print(f"  Joke: {joke['text']}")
    else:
        print("Could not generate query embedding due to quota exhaustion.")
else:
    print("Could not complete joke embedding generation due to quota exhaustion.")
