import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
from pathlib import Path
import faiss
import numpy as np
import requests
import json
import time

print("🔧 Initializing FAISS with Ollama integration...")

# -- CONFIG --
CHUNK_SIZE = 40
CHUNK_OVERLAP = 10
DOC_PATH = Path("documents")
print(f"📁 Using document path: {DOC_PATH}")
print(f"⚙️ Configuration: Chunk size={CHUNK_SIZE}, Overlap={CHUNK_OVERLAP}")

# -- HELPERS --

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    print(f"  → Splitting text into chunks (size={size}, overlap={overlap})")
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        if chunk:
            chunks.append(chunk)
    print(f"  → Created {len(chunks)} chunks")
    return chunks

def get_embedding(text: str) -> np.ndarray:
    print(f"  → Getting embedding for text (length: {len(text)} chars)")
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={
                "model": "nomic-embed-text",
                "prompt": text
            }
        )
        response.raise_for_status()
        embedding = np.array(response.json()["embedding"], dtype=np.float32)
        print(f"  → Successfully generated embedding (dimension: {len(embedding)})")
        return embedding
    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        raise

# -- LOAD DOCS & CHUNK --
print("\n📂 Starting document processing...")
print("=" * 50)

all_chunks = []
metadata = []

for file in DOC_PATH.glob("*.txt"):
    print(f"\n📄 Processing file: {file.name}")
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"  → Read {len(content)} characters")
            chunks = chunk_text(content)
            
            for idx, chunk in enumerate(chunks):
                print(f"  → Processing chunk {idx + 1}/{len(chunks)}")
                embedding = get_embedding(chunk)
                all_chunks.append(embedding)
                metadata.append({
                    "doc_name": file.name,
                    "chunk": chunk,
                    "chunk_id": f"{file.stem}_{idx}"
                })
        print(f"✅ Successfully processed {file.name}")
        time.sleep(1)  # Small delay between files to avoid overwhelming Ollama
    except Exception as e:
        print(f"❌ Error processing {file.name}: {e}")
        continue

print(f"\n📊 Processed {len(all_chunks)} chunks from {len(list(DOC_PATH.glob('*.txt')))} documents")

# -- CREATE FAISS INDEX --
print("\n🔨 Creating FAISS index")
print("=" * 50)

try:
    dimension = len(all_chunks[0])
    print(f"📏 Vector dimension: {dimension}")
    index = faiss.IndexFlatL2(dimension)
    print("  → Adding vectors to index...")
    index.add(np.stack(all_chunks))
    print(f"✅ Index created successfully with {len(all_chunks)} vectors")
except Exception as e:
    print(f"❌ Error creating FAISS index: {e}")
    raise

# -- SEARCH --
print("\n🔍 Running example search")
print("=" * 50)

query = "When will Dhoni retire?"
print(f"Query: {query}")

try:
    print("  → Generating query embedding...")
    query_vec = get_embedding(query).reshape(1, -1)
    print("  → Searching index...")
    D, I = index.search(query_vec, k=3)
    
    print("\n📚 Top Matches:")
    for rank, idx in enumerate(I[0]):
        data = metadata[idx]
        print(f"\n#{rank + 1}: From {data['doc_name']} [{data['chunk_id']}]")
        print(f"Distance: {D[0][rank]:.4f}")
        print(f"Content: {data['chunk']}")
except Exception as e:
    print(f"❌ Error during search: {e}")
    raise

print("\n✨ Processing complete!")
