import os
import time
import random
from datetime import datetime, timedelta
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import google.generativeai as genai
import numpy as np
from dotenv import load_dotenv

load_dotenv()
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

def get_embedding(text: str, task_type: str, max_retries=3) -> np.ndarray:
    """Get embedding for text using specified task type with retry logic"""
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED
    
    for attempt in range(max_retries):
        try:
            # Check quota status first
            if not check_quota_status():
                continue
                
            result = genai.embed_content(
                model="models/gemini-embedding-exp-03-07",
                content=text,
                task_type=task_type
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

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Focus on the most informative comparisons
comparisons = {
    "CLUSTERING": {
        "name": "Clustering Test",
        "pairs": [
            ("The cat sat on the mat", "The feline rested on the rug", "Similar meaning"),
            ("The cat sat on the mat", "The dog played in the yard", "Different meaning")
        ]
    },
    "RETRIEVAL_DOCUMENT": {
        "name": "Retrieval Test",
        "pairs": [
            ("How does AlphaFold work?", "AlphaFold is an AI system that predicts protein structures", "Matching Q-A"),
            ("How does AlphaFold work?", "Paris is the capital of France", "Non-matching Q-A")
        ]
    },
    "SEMANTIC_SIMILARITY": {
        "name": "Semantic Similarity Test",
        "pairs": [
            ("The quick brown fox jumps over the lazy dog", "A fast brown fox leaps over a sleepy dog", "Paraphrase"),
            ("The quick brown fox jumps over the lazy dog", "It's raining outside", "Different topic")
        ]
    }
}

def process_task_type(task_type: str, test: dict) -> None:
    """Process a single task type with quota management"""
    print(f"\n📊 Task Type: {task_type}")
    print("=" * 50)
    print(f"Test: {test['name']}")
    
    try:
        # Get embeddings for all texts first
        all_texts = set()
        for pair in test['pairs']:
            all_texts.add(pair[0])
            all_texts.add(pair[1])
        
        print("\nGenerating embeddings...")
        embeddings = {}
        for text in all_texts:
            print(f"Getting embedding for: {text}")
            embedding = get_embedding(text, task_type)
            if embedding is None:  # Quota exhausted
                print("Skipping remaining embeddings due to quota exhaustion")
                return
            embeddings[text] = embedding
            time.sleep(2)  # Conservative delay between calls
        
        # Compare pairs
        print("\nComparison Results:")
        for text1, text2, description in test['pairs']:
            sim = cosine_similarity(embeddings[text1], embeddings[text2])
            print(f"\n{description}:")
            print(f"A: {text1}")
            print(f"B: {text2}")
            print(f"Similarity: {sim:.4f}")
            
            if sim > 0.9:
                print("Interpretation: Very similar")
            elif sim > 0.8:
                print("Interpretation: Moderately similar")
            elif sim > 0.7:
                print("Interpretation: Somewhat similar")
            else:
                print("Interpretation: Not very similar")
        
    except Exception as e:
        print(f"Error processing task type {task_type}: {str(e)}")

# Main execution
print("🔍 Comparing Different Task Types\n")

# Compare each task type
for task_type, test in comparisons.items():
    process_task_type(task_type, test)

print("\n📝 Task Type Explanations:")
print("1. CLUSTERING: Best for grouping similar items together")
print("2. RETRIEVAL_DOCUMENT: Best for finding relevant documents")
print("3. SEMANTIC_SIMILARITY: Best for measuring text similarity") 