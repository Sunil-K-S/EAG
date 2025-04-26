import os
from pathlib import Path
import faiss
import numpy as np
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import json
import pickle

# Load environment variables
load_dotenv()

# Quota management
QUOTA_RESET_TIME = None
QUOTA_EXHAUSTED = False
MIN_WAIT_TIME = 60  # Minimum wait time in seconds
MAX_WAIT_TIME = 300  # Maximum wait time in seconds
current_wait_time = MIN_WAIT_TIME

# Progress tracking
PROGRESS_FILE = "faiss_progress.pkl"
METADATA_FILE = "faiss_metadata.json"

def save_progress(chunks, metadata):
    """Save current progress to disk"""
    try:
        with open(PROGRESS_FILE, 'wb') as f:
            pickle.dump(chunks, f)
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        print("💾 Progress saved successfully")
    except Exception as e:
        print(f"⚠️ Could not save progress: {e}")

def load_progress():
    """Load progress from disk if available"""
    try:
        if os.path.exists(PROGRESS_FILE) and os.path.exists(METADATA_FILE):
            with open(PROGRESS_FILE, 'rb') as f:
                chunks = pickle.load(f)
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            print(f"📂 Loaded {len(chunks)} previously processed chunks")
            return chunks, metadata
    except Exception as e:
        print(f"⚠️ Could not load progress: {e}")
    return [], []

def check_quota_status() -> bool:
    """
    Check if we should wait due to quota exhaustion.
    
    Returns:
        bool: True if we can proceed, False if we should wait
    """
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED, current_wait_time
    
    if not QUOTA_EXHAUSTED:
        return True
        
    if QUOTA_RESET_TIME and datetime.now() < QUOTA_RESET_TIME:
        wait_seconds = (QUOTA_RESET_TIME - datetime.now()).total_seconds()
        print(f"⏳ Quota exhausted. Waiting {wait_seconds:.0f} seconds until reset...")
        time.sleep(wait_seconds)
        QUOTA_EXHAUSTED = False
        QUOTA_RESET_TIME = None
        current_wait_time = MIN_WAIT_TIME  # Reset wait time
        return True
        
    return False

# Initialize Gemini client
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    print("✅ Gemini client initialized successfully")
except Exception as e:
    print(f"❌ Error initializing Gemini client: {e}")
    raise

# Configuration constants
CHUNK_SIZE = 40  # Number of words per chunk
CHUNK_OVERLAP = 10  # Number of words to overlap between chunks
DOC_PATH = Path("documents")  # Path to documents directory

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """
    Split text into overlapping chunks.
    
    Args:
        text (str): Input text to chunk
        size (int): Size of each chunk in words
        overlap (int): Number of words to overlap between chunks
    
    Returns:
        list: List of text chunks
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        if chunk:
            chunks.append(chunk)
    return chunks

def get_embedding(text: str, max_retries: int = 3) -> np.ndarray:
    """
    Get embedding for text using Gemini API with retry logic.
    
    Args:
        text (str): Text to get embedding for
        max_retries (int): Maximum number of retry attempts
    
    Returns:
        np.ndarray: Embedding vector
    """
    global QUOTA_RESET_TIME, QUOTA_EXHAUSTED, current_wait_time
    
    for attempt in range(max_retries):
        try:
            if not check_quota_status():
                # If quota is exhausted, wait with increasing backoff
                print(f"⏳ Waiting {current_wait_time} seconds before retry...")
                time.sleep(current_wait_time)
                current_wait_time = min(current_wait_time * 2, MAX_WAIT_TIME)  # Exponential backoff with cap
                continue
                
            result = genai.embed_content(
                model="models/gemini-embedding-exp-03-07",
                content=text,
                task_type="RETRIEVAL_DOCUMENT"
            )
            current_wait_time = MIN_WAIT_TIME  # Reset wait time on success
            return np.array(result['embedding'], dtype=np.float32)
            
        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e):
                QUOTA_EXHAUSTED = True
                QUOTA_RESET_TIME = datetime.now() + timedelta(minutes=1)
                print(f"⚠️ Quota exhausted. Will retry after {current_wait_time} seconds...")
                time.sleep(current_wait_time)
                current_wait_time = min(current_wait_time * 2, MAX_WAIT_TIME)  # Exponential backoff with cap
                continue
                
            if attempt == max_retries - 1:
                print(f"❌ Failed to get embedding after {max_retries} attempts: {e}")
                raise
            print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(5 * (attempt + 1))  # Exponential backoff

# Initialize lists for chunks and metadata
all_chunks, metadata = load_progress()
processed_files = {item['doc_name'] for item in metadata}

print(f"\n📂 Processing documents from {DOC_PATH}")
print("=" * 50)

# Process each document
for file in DOC_PATH.glob("*.txt"):
    if file.name in processed_files:
        print(f"⏩ Skipping already processed file: {file.name}")
        continue
        
    print(f"\n📄 Processing {file.name}")
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            chunks = chunk_text(content)
            print(f"  → Split into {len(chunks)} chunks")
            
            for idx, chunk in enumerate(chunks):
                print(f"  → Getting embedding for chunk {idx + 1}/{len(chunks)}")
                embedding = get_embedding(chunk)
                all_chunks.append(embedding)
                metadata.append({
                    "doc_name": file.name,
                    "chunk": chunk,
                    "chunk_id": f"{file.stem}_{idx}"
                })
                time.sleep(1)  # Small delay between API calls
            
            processed_files.add(file.name)
            print(f"✅ Successfully processed {file.name}")
            save_progress(all_chunks, metadata)  # Save progress after each file
            
    except Exception as e:
        print(f"❌ Error processing {file.name}: {e}")
        save_progress(all_chunks, metadata)  # Save progress even on error
        continue

if not all_chunks:
    print("❌ No documents were processed successfully")
    exit(1)

print("\n🔨 Creating FAISS index")
print("=" * 50)

# Create and populate FAISS index
try:
    dimension = len(all_chunks[0])
    index = faiss.IndexFlatL2(dimension)
    index.add(np.stack(all_chunks))
    print(f"✅ Index created successfully with {len(all_chunks)} vectors")
except Exception as e:
    print(f"❌ Error creating FAISS index: {e}")
    raise

# Example search
print("\n🔍 Running example search")
print("=" * 50)

query = "When will Dhoni retire?"
print(f"Query: {query}")

try:
    query_vec = get_embedding(query).reshape(1, -1)  # Reshape for FAISS
    D, I = index.search(query_vec, k=3)  # Get top 3 matches
    
    print("\n📚 Top Matches:")
    for rank, idx in enumerate(I[0]):
        data = metadata[idx]
        print(f"\n#{rank + 1}: From {data['doc_name']} [{data['chunk_id']}]")
        print(f"Distance: {D[0][rank]:.4f}")
        print(f"Content: {data['chunk']}")
except Exception as e:
    print(f"❌ Error during search: {e}")
    raise
