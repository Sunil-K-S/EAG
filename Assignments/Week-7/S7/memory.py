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

    def _get_embedding(self, text: str) -> np.ndarray:
        response = requests.post(
            self.embedding_model_url,
            json={"model": self.model_name, "prompt": text}
        )
        response.raise_for_status()
        return np.array(response.json()["embedding"], dtype=np.float32)

    def add(self, item: MemoryItem):
        emb = self._get_embedding(item.text)
        self.embeddings.append(emb)
        self.data.append(item)

        # Initialize or add to index
        if self.index is None:
            self.index = faiss.IndexFlatL2(len(emb))
        self.index.add(np.stack([emb]))
        
        # Save after adding
        self._save_index()

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        type_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None,
        session_filter: Optional[str] = None,
        video_id: Optional[str] = None,
        timestamp_range: Optional[tuple[str, str]] = None
    ) -> List[MemoryItem]:
        if not self.index or len(self.data) == 0:
            return []

        query_vec = self._get_embedding(query).reshape(1, -1)
        D, I = self.index.search(query_vec, top_k * 2)  # Overfetch to allow filtering

        results = []
        for idx in I[0]:
            if idx >= len(self.data):
                continue
            item = self.data[idx]

            # Filter by type
            if type_filter and item.type != type_filter:
                continue

            # Filter by tags
            if tag_filter and not any(tag in item.tags for tag in tag_filter):
                continue

            # Filter by session
            if session_filter and item.session_id != session_filter:
                continue

            # Filter by video ID
            if video_id and (not item.youtube_metadata or item.youtube_metadata.video_id != video_id):
                continue

            # Filter by timestamp range
            if timestamp_range and item.youtube_metadata:
                start_time, end_time = timestamp_range
                if not (start_time <= item.youtube_metadata.timestamp <= end_time):
                    continue

            results.append(item)
            if len(results) >= top_k:
                break

        return results

    def bulk_add(self, items: List[MemoryItem]):
        for item in items:
            self.add(item)

    def get_video_chunks(self, video_id: str) -> List[MemoryItem]:
        """Get all chunks for a specific video."""
        return [item for item in self.data 
                if item.type == "youtube_chunk" 
                and item.youtube_metadata 
                and item.youtube_metadata.video_id == video_id]

    def delete_video_chunks(self, video_id: str):
        """Delete all chunks for a specific video."""
        to_keep = []
        for i, item in enumerate(self.data):
            if not (item.type == "youtube_chunk" 
                   and item.youtube_metadata 
                   and item.youtube_metadata.video_id == video_id):
                to_keep.append(i)
        
        if to_keep:
            self.data = [self.data[i] for i in to_keep]
            self.embeddings = [self.embeddings[i] for i in to_keep]
            self.index = faiss.IndexFlatL2(len(self.embeddings[0]))
            self.index.add(np.stack(self.embeddings))
            self._save_index()
