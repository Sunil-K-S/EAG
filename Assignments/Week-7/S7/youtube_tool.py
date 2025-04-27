from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from memory import MemoryManager, MemoryItem
import faiss
import numpy as np
import requests
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
import os
from bs4 import BeautifulSoup

class YouTubeVideoInput(BaseModel):
    url: str
    action: str  # "process" or "search"
    query: Optional[str] = None

class YouTubeVideoOutput(BaseModel):
    status: str
    message: str
    data: Optional[Dict] = None

class YouTubeTool:
    def __init__(self):
        self.memory = MemoryManager()
        self.video_index = None
        self.metadata = []
        self.processed_videos = set()

    async def process_video(self, url: str) -> YouTubeVideoOutput:
        try:
            # Get video ID for filtering
            video_id = self._extract_video_id(url)
            print(f"[youtube_tool] ===== STARTING VIDEO PROCESSING =====")
            print(f"[youtube_tool] Processing video: {video_id}")
            
            # Clear ALL YouTube items from memory
            print(f"[youtube_tool] Clearing existing memory...")
            # Instead of clear_items, we'll reset the memory manager
            self.memory = MemoryManager()  # Create a new instance
            print(f"[youtube_tool] Cleared all YouTube items from memory")
            
            # Clear the FAISS index files
            print(f"[youtube_tool] Removing existing index files...")
            index_files = [
                os.path.join(self.memory.index_path, "index.bin"),
                os.path.join(self.memory.index_path, "metadata.json"),
                os.path.join(self.memory.index_path, "embeddings.npy")
            ]
            for file in index_files:
                if os.path.exists(file):
                    print(f"[youtube_tool] Removing index file: {file}")
                    os.remove(file)
                else:
                    print(f"[youtube_tool] Index file not found: {file}")
            
            # Reset the memory manager's state
            print(f"[youtube_tool] Resetting memory manager state...")
            self.memory.index = None
            self.memory.data = []
            self.memory.embeddings = []
            print(f"[youtube_tool] Memory manager reset complete")
            
            # Get transcript using YouTube API
            try:
                print(f"[youtube_tool] Fetching transcript...")
                transcript_data = await self._get_transcript(url)
                if not transcript_data:
                    error_msg = "Failed to get transcript: Empty transcript data"
                    print(f"[youtube_tool] {error_msg}")
                    return YouTubeVideoOutput(status="error", message=error_msg)
                
                print(f"[youtube_tool] Retrieved transcript with {len(transcript_data)} segments")
                
                # Calculate video duration from transcript
                last_segment = transcript_data[-1]
                video_duration = last_segment['start'] + last_segment['duration']
                print(f"[youtube_tool] Video duration from transcript: {video_duration} seconds ({int(video_duration/60):02d}:{int(video_duration%60):02d})")
                
                # Verify transcript duration is reasonable
                if video_duration > 3600:  # More than 1 hour
                    print(f"[youtube_tool] Warning: Unusually long video duration: {video_duration} seconds")
                
            except Exception as e:
                error_msg = f"Failed to get transcript: {str(e)}"
                print(f"[youtube_tool] {error_msg}")
                return YouTubeVideoOutput(status="error", message=error_msg)
            
            # Split into chunks with timestamps
            print(f"[youtube_tool] Creating chunks from transcript...")
            chunks = self._chunk_with_timestamps(transcript_data)
            print(f"[youtube_tool] Created {len(chunks)} chunks from transcript")
            
            # Generate embeddings and store in memory
            print(f"[youtube_tool] Adding chunks to memory and generating embeddings...")
            for i, chunk in enumerate(chunks):
                print(f"[youtube_tool] Adding chunk {i+1}/{len(chunks)}: start={chunk['start']}s, timestamp={chunk['timestamp']}")
                try:
                    self.memory.add(MemoryItem(
                        text=chunk['text'],
                        type="youtube_chunk",
                        tool_name="youtube_tool",
                        user_query=url,
                        tags=["youtube", video_id],
                        metadata={
                            "timestamp": chunk['timestamp'],
                            "start": chunk['start'],
                            "duration": chunk['duration']
                        }
                    ))
                except Exception as e:
                    error_msg = f"Failed to add chunk {i+1}: {str(e)}"
                    print(f"[youtube_tool] {error_msg}")
                    return YouTubeVideoOutput(status="error", message=error_msg)
            
            print(f"[youtube_tool] Added {len(chunks)} chunks to memory")
            print(f"[youtube_tool] ===== VIDEO PROCESSING COMPLETE =====")
            
            return YouTubeVideoOutput(
                status="success",
                message=f"Processed {len(chunks)} chunks from video",
                data={"chunks_processed": len(chunks)}
            )
            
        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            print(f"[youtube_tool] {error_msg}")
            return YouTubeVideoOutput(
                status="error",
                message=error_msg
            )

    async def search_video(self, query: str, url: str) -> YouTubeVideoOutput:
        try:
            print(f"[youtube_tool] ===== STARTING VIDEO SEARCH =====")
            print(f"[youtube_tool] Starting search with query: {query}, url: {url}")
            
            # Get video ID for filtering
            video_id = self._extract_video_id(url)
            print(f"[youtube_tool] Extracted video ID: {video_id}")
            
            # Check if video is already processed
            print(f"[youtube_tool] Checking if video {video_id} is already processed")
            # Use a dummy query instead of empty string
            existing_items = self.memory.retrieve(
                query="check video",  # Use a dummy query instead of empty string
                top_k=1,
                tag_filter=["youtube", video_id]
            )
            
            # Check if existing items have reasonable timestamps
            should_reprocess = False
            if existing_items:
                print(f"[youtube_tool] Found existing items, checking timestamps...")
                for item in existing_items:
                    if item.metadata and "start" in item.metadata:
                        start_time = item.metadata["start"]
                        print(f"[youtube_tool] Checking timestamp: {start_time}s ({int(start_time/60):02d}:{int(start_time%60):02d})")
                        
                        # More strict validation:
                        # 1. Check if timestamp is unreasonably large (more than 1 hour)
                        # 2. Check if timestamp is negative
                        # 3. Check if timestamp is not a number
                        if not isinstance(start_time, (int, float)):
                            print(f"[youtube_tool] Warning: Invalid timestamp type: {type(start_time)}")
                            should_reprocess = True
                            break
                        elif start_time < 0:
                            print(f"[youtube_tool] Warning: Negative timestamp found: {start_time}s")
                            should_reprocess = True
                            break
                        elif start_time > 3600:  # More than 1 hour
                            print(f"[youtube_tool] Warning: Unusually large timestamp found: {start_time}s")
                            should_reprocess = True
                            break
            
            if not existing_items or should_reprocess:
                print(f"[youtube_tool] Video {video_id} not found in memory or needs reprocessing")
                print(f"[youtube_tool] Starting reprocessing...")
                # Process the video first
                process_result = await self.process_video(url)
                if process_result.status != "success":
                    error_msg = f"Failed to process video: {process_result.message}"
                    print(f"[youtube_tool] {error_msg}")
                    return YouTubeVideoOutput(status="error", message=error_msg)
                print(f"[youtube_tool] Reprocessing complete")
            else:
                print(f"[youtube_tool] Using existing processed video")
            
            # Search memory for relevant chunks
            print(f"[youtube_tool] Searching memory for query: {query}")
            results = self.memory.retrieve(
                query=query,
                top_k=3,
                tag_filter=["youtube", video_id]
            )
            print(f"[youtube_tool] Retrieved {len(results)} results")
            
            # Format results with timestamps and similarity scores
            formatted_results = []
            for i, item in enumerate(results):
                if item.metadata and "start" in item.metadata:
                    # Convert timestamp to seconds for seeking
                    start_seconds = item.metadata["start"]
                    
                    # Format timestamp for display (MM:SS)
                    minutes = int(start_seconds // 60)
                    seconds = int(start_seconds % 60)
                    display_timestamp = f"{minutes:02d}:{seconds:02d}"
                    
                    print(f"[youtube_tool] Result {i}: start_seconds={start_seconds}, display_timestamp={display_timestamp}")
                    
                    formatted_results.append({
                        "timestamp": display_timestamp,
                        "start": start_seconds,
                        "text": item.text,
                        "score": 1.0
                    })
            
            print(f"[youtube_tool] Formatted {len(formatted_results)} results")
            print(f"[youtube_tool] ===== VIDEO SEARCH COMPLETE =====")
            
            return YouTubeVideoOutput(
                status="success",
                message=f"Found {len(formatted_results)} relevant segments",
                data={"results": formatted_results}
            )
            
        except Exception as e:
            error_msg = f"Error searching video: {str(e)}"
            print(f"[youtube_tool] {error_msg}")
            print(f"[youtube_tool] Error type: {type(e).__name__}")
            import traceback
            print(f"[youtube_tool] Error traceback: {traceback.format_exc()}")
            return YouTubeVideoOutput(
                status="error",
                message=error_msg
            )

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'(?:youtube\.com\/embed\/)([^&\n?#]+)',
            r'(?:youtube\.com\/v\/)([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError("Invalid YouTube URL")

    async def _get_transcript(self, url: str) -> List[Dict]:
        """Get transcript with timestamps using youtube-transcript-api."""
        try:
            video_id = self._extract_video_id(url)
            print(f"[youtube_tool] Getting transcript for video ID: {video_id}")
            
            try:
                # Get transcript
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                print(f"[youtube_tool] Successfully got transcript with {len(transcript_list)} segments")
                
                # Calculate video duration from transcript
                if transcript_list:
                    last_segment = transcript_list[-1]
                    video_duration = last_segment['start'] + last_segment['duration']
                    print(f"[youtube_tool] Estimated video duration from transcript: {video_duration} seconds ({int(video_duration/60):02d}:{int(video_duration%60):02d})")
                else:
                    print("[youtube_tool] Empty transcript")
                    video_duration = None
                
                # Validate transcript data
                for i, segment in enumerate(transcript_list):
                    if not isinstance(segment, dict):
                        print(f"[youtube_tool] Invalid segment format at index {i}: {segment}")
                        continue
                    if 'start' not in segment or 'duration' not in segment or 'text' not in segment:
                        print(f"[youtube_tool] Missing required fields in segment {i}: {segment}")
                        continue
                    if not isinstance(segment['start'], (int, float)) or not isinstance(segment['duration'], (int, float)):
                        print(f"[youtube_tool] Invalid timestamp format in segment {i}: {segment}")
                        continue
                    if segment['start'] < 0 or segment['duration'] <= 0:
                        print(f"[youtube_tool] Invalid timestamp values in segment {i}: start={segment['start']}, duration={segment['duration']}")
                        continue
                
                # Log first few segments to check timestamps
                print("[youtube_tool] First 3 transcript segments:")
                for i, segment in enumerate(transcript_list[:3]):
                    print(f"[youtube_tool] Segment {i}: start={segment['start']}s, duration={segment['duration']}s, text={segment['text'][:50]}...")
                
                # Log last few segments to check timestamps
                print("[youtube_tool] Last 3 transcript segments:")
                for i, segment in enumerate(transcript_list[-3:]):
                    print(f"[youtube_tool] Segment {len(transcript_list)-3+i}: start={segment['start']}s, duration={segment['duration']}s, text={segment['text'][:50]}...")
                
                return transcript_list
                
            except Exception as e:
                print(f"[youtube_tool] Error getting transcript from YouTube API: {str(e)}")
                # Try getting transcript in English if available
                try:
                    print(f"[youtube_tool] Trying to get English transcript...")
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                    print(f"[youtube_tool] Successfully got English transcript with {len(transcript_list)} segments")
                except Exception as e2:
                    print(f"[youtube_tool] Error getting English transcript: {str(e2)}")
                    raise Exception(f"Failed to get transcript in any language: {str(e2)}")
            
        except Exception as e:
            error_msg = f"Failed to get transcript: {str(e)}"
            print(f"[youtube_tool] {error_msg}")
            raise Exception(error_msg)

    def _chunk_with_timestamps(self, transcript_data: List[Dict]) -> List[Dict]:
        """Create chunks from transcript data while preserving timestamps."""
        chunks = []
        current_chunk = []
        current_start = None
        max_chunk_duration = 30  # seconds
        min_chunk_duration = 10  # seconds
        
        print(f"[youtube_tool] Processing transcript with {len(transcript_data)} segments")
        
        # Validate transcript data
        for segment in transcript_data:
            if not isinstance(segment, dict):
                print(f"[youtube_tool] Invalid segment format: {segment}")
                continue
            if 'start' not in segment or 'duration' not in segment or 'text' not in segment:
                print(f"[youtube_tool] Missing required fields in segment: {segment}")
                continue
            if not isinstance(segment['start'], (int, float)) or not isinstance(segment['duration'], (int, float)):
                print(f"[youtube_tool] Invalid timestamp format in segment: {segment}")
                continue
        
        for i, segment in enumerate(transcript_data):
            if not current_chunk:
                current_start = segment['start']
                print(f"[youtube_tool] Starting new chunk at segment {i}, time: {current_start}s")
            
            current_chunk.append(segment)
            
            # Calculate duration of current chunk
            current_duration = segment['start'] + segment['duration'] - current_start
            print(f"[youtube_tool] Segment {i}: start={segment['start']}s, duration={segment['duration']}s, current_duration={current_duration}s")
            
            # If chunk is long enough or we're at the end, create a new chunk
            if current_duration >= max_chunk_duration or segment == transcript_data[-1]:
                if current_duration >= min_chunk_duration:
                    # Combine text from all segments in the chunk
                    chunk_text = ' '.join(s['text'] for s in current_chunk)
                    
                    # Use the start time of the first segment in the chunk
                    start_time = current_chunk[0]['start']
                    
                    # Validate start time is reasonable (less than 24 hours)
                    if start_time > 86400:  # 24 hours in seconds
                        print(f"[youtube_tool] Warning: Unusually large start time: {start_time}s")
                        continue
                    
                    # Format timestamp
                    minutes = int(start_time // 60)
                    seconds = int(start_time % 60)
                    timestamp = f"{minutes:02d}:{seconds:02d}"
                    
                    print(f"[youtube_tool] Creating chunk: start_time={start_time}s, timestamp={timestamp}, duration={current_duration}s")
                    
                    chunks.append({
                        "text": chunk_text,
                        "timestamp": timestamp,
                        "start": start_time,
                        "duration": current_duration
                    })
                
                current_chunk = []
        
        print(f"[youtube_tool] Created {len(chunks)} chunks total")
        return chunks

    async def reprocess_video(self, url: str) -> YouTubeVideoOutput:
        """Force reprocess a video by clearing all data and processing again."""
        print(f"[youtube_tool] Forcing reprocess of video: {url}")
        return await self.process_video(url) 