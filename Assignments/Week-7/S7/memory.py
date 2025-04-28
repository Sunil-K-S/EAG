# memory.py

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import numpy as np
import faiss
import requests
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import json
import time

def log(stage: str, msg: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{stage}] {msg}")

class YouTubeChunkMetadata(BaseModel):
    video_id: str
    timestamp: str
    chunk_index: int
    total_chunks: int

class MemoryItem(BaseModel):
    text: str
    type: Literal["preference", "tool_output", "fact", "query", "system", "youtube_chunk", "search_result"] = "fact"
    timestamp: Optional[str] = datetime.now().isoformat()
    tool_name: Optional[str] = None
    user_query: Optional[str] = None
    tags: List[str] = []
    session_id: Optional[str] = None
    youtube_metadata: Optional[YouTubeChunkMetadata] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryItem':
        # Handle old format where text might be in a different field
        if 'text' not in data and 'doc' in data:
            data['text'] = data['doc']
        return cls(**data)

class MemoryManager:
    def __init__(self, embedding_model_url="http://localhost:11434/api/embeddings", model_name="nomic-embed-text", index_path="faiss_index"):
        self.embedding_model_url = embedding_model_url
        self.model_name = model_name
        self.index = None
        self.data: List[MemoryItem] = []
        self.embeddings: List[np.ndarray] = []
        self.index_path = index_path
        self._load_index()

    def _load_index(self):
        """Load FAISS index and metadata if they exist."""
        try:
            if os.path.exists(os.path.join(self.index_path, "index.bin")):
                self.index = faiss.read_index(os.path.join(self.index_path, "index.bin"))
                with open(os.path.join(self.index_path, "metadata.json"), "r") as f:
                    self.data = [MemoryItem.from_dict(item) for item in json.load(f)]
                with open(os.path.join(self.index_path, "embeddings.npy"), "rb") as f:
                    self.embeddings = list(np.load(f))
                log("memory", f"Loaded index with {len(self.data)} items")
            else:
                log("memory", "No existing index found, starting fresh")
                self.index = None
                self.data = []
                self.embeddings = []
        except Exception as e:
            log("memory", f"⚠️ Failed to load index: {e}")
            self.index = None
            self.data = []
            self.embeddings = []

    def _save_index(self):
        """Save FAISS index and metadata."""
        try:
            os.makedirs(self.index_path, exist_ok=True)
            if self.index:
                faiss.write_index(self.index, os.path.join(self.index_path, "index.bin"))
            with open(os.path.join(self.index_path, "metadata.json"), "w") as f:
                json.dump([item.dict() for item in self.data], f)
            if self.embeddings:
                np.save(os.path.join(self.index_path, "embeddings.npy"), np.stack(self.embeddings))
            log("memory", f"Saved index with {len(self.data)} items")
        except Exception as e:
            log("memory", f"⚠️ Failed to save index: {e}")
            raise  # Re-raise to handle at higher level

    def _get_embedding(self, text: str, max_retries: int = 3) -> np.ndarray:
        """Get embedding with retries and error handling."""
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.embedding_model_url,
                    json={"model": self.model_name, "prompt": text},
                    timeout=10  # Add timeout
                )
                response.raise_for_status()
                embedding = np.array(response.json()["embedding"], dtype=np.float32)
                
                # Validate embedding
                if embedding.size == 0:
                    raise ValueError("Empty embedding received")
                if not np.all(np.isfinite(embedding)):
                    raise ValueError("Invalid values in embedding")
                    
                return embedding
            except Exception as e:
                last_error = e
                log("memory", f"⚠️ Embedding attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                    continue
        raise last_error

    def add(self, item: MemoryItem):
        """Add item to memory with validation and error handling."""
        try:
            # Validate item
            if not item.text.strip():
                raise ValueError("Empty text in memory item")
                
            # Get embedding
            emb = self._get_embedding(item.text)
            self.embeddings.append(emb)
            self.data.append(item)

            # Log the item being added
            log("memory", f"Adding item with text: '{item.text[:50]}...', tags: {item.tags}")

            # Initialize or add to index
            if self.index is None:
                self.index = faiss.IndexFlatL2(len(emb))
            self.index.add(np.stack([emb]))
            
            # Save after adding
            self._save_index()
            
        except Exception as e:
            log("memory", f"❌ Failed to add item: {e}")
            raise

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        type_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None,
        session_filter: Optional[str] = None,
        video_id: Optional[str] = None,
        timestamp_range: Optional[tuple[str, str]] = None,
        min_score: float = 0.0
    ) -> List[MemoryItem]:
        """Retrieve items from memory with improved filtering and scoring."""
        if not self.index or len(self.data) == 0:
            log("memory", "No index or data available for retrieval")
            return []

        try:
            # Get query embedding
            query_vec = self._get_embedding(query).reshape(1, -1)
            
            # Search with larger k to allow for filtering
            k = min(top_k * 4, len(self.data))  # Get 4x results for filtering
            D, I = self.index.search(query_vec, k)
            
            # Convert distances to scores (1 / (1 + distance))
            scores = 1 / (1 + D[0])

            log("memory", f"Search results indices: {I[0]}")
            log("memory", f"Search scores: {scores}")

            results = []
            for idx, score in zip(I[0], scores):
                if idx >= len(self.data) or score < min_score:
                    continue
                    
                item = self.data[idx]
                
                # Apply filters
                if not self._passes_filters(
                    item, 
                    type_filter, 
                    tag_filter, 
                    session_filter, 
                    video_id, 
                    timestamp_range
                ):
                    continue

                # Add score to metadata
                item_with_score = item.copy()
                if item_with_score.metadata is None:
                    item_with_score.metadata = {}
                item_with_score.metadata['score'] = float(score)
                
                results.append(item_with_score)
                if len(results) >= top_k:
                    break

            log("memory", f"Final retrieved results count: {len(results)}")
            return results

        except Exception as e:
            log("memory", f"❌ Error during retrieval: {e}")
            return []

    def _passes_filters(
        self,
        item: MemoryItem,
        type_filter: Optional[str],
        tag_filter: Optional[List[str]],
        session_filter: Optional[str],
        video_id: Optional[str],
        timestamp_range: Optional[tuple[str, str]]
    ) -> bool:
        """Check if item passes all filters."""
        # Type filter
        if type_filter and item.type != type_filter:
            return False

        # Tag filter
        if tag_filter and not any(tag in item.tags for tag in tag_filter):
            return False

        # Session filter
        if session_filter and item.session_id != session_filter:
            return False

        # Video ID filter
        if video_id and (not item.youtube_metadata or item.youtube_metadata.video_id != video_id):
            return False

        # Timestamp range filter
        if timestamp_range and item.youtube_metadata:
            start_time, end_time = timestamp_range
            if not (start_time <= item.youtube_metadata.timestamp <= end_time):
                return False

        return True

    def bulk_add(self, items: List[MemoryItem]):
        """Add multiple items efficiently."""
        for item in items:
            try:
                self.add(item)
            except Exception as e:
                log("memory", f"❌ Failed to add item in bulk: {e}")
                continue

    def get_video_chunks(self, video_id: str) -> List[MemoryItem]:
        """Get all chunks for a specific video."""
        return [item for item in self.data 
                if item.type == "youtube_chunk" 
                and item.youtube_metadata 
                and item.youtube_metadata.video_id == video_id]

    def delete_video_chunks(self, video_id: str):
        """Delete all chunks for a specific video and rebuild index."""
        try:
            to_keep = []
            for i, item in enumerate(self.data):
                if not (item.type == "youtube_chunk" 
                       and item.youtube_metadata 
                       and item.youtube_metadata.video_id == video_id):
                    to_keep.append(i)
            
            if to_keep:
                self.data = [self.data[i] for i in to_keep]
                self.embeddings = [self.embeddings[i] for i in to_keep]
                
                # Rebuild index
                if self.embeddings:
                    self.index = faiss.IndexFlatL2(len(self.embeddings[0]))
                    self.index.add(np.stack(self.embeddings))
                else:
                    self.index = None
                    
                self._save_index()
                log("memory", f"Deleted chunks for video {video_id} and rebuilt index")
            
        except Exception as e:
            log("memory", f"❌ Failed to delete video chunks: {e}")
            raise
