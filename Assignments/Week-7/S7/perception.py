from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
import json
import time
from request_types import RequestContext

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str, request_context: RequestContext = None):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        request_id = f"[{request_context.request_id}] " if request_context else ""
        duration = f" (took {request_context.stage_times.get(stage, 0):.2f}s)" if request_context else ""
        print(f"[{now}] {request_id}[{stage}]{duration} {msg}")

load_dotenv()

# Configure the API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class YouTubeMetadata(BaseModel):
    video_id: Optional[str] = None
    timestamp: Optional[str] = None
    action: Optional[str] = None  # "process" or "search"

class Perception(BaseModel):
    user_input: str
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tool_hint: Optional[str] = "search_tool"  # Generic tool name

def extract_youtube_metadata(input_text: str) -> YouTubeMetadata:
    """Extracts YouTube-specific metadata from input text."""
    metadata = YouTubeMetadata()
    
    # Extract video ID from URL if present
    video_id_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', input_text)
    if video_id_match:
        metadata.video_id = video_id_match.group(1)
    
    # Extract timestamp if present
    timestamp_match = re.search(r'(\d{1,2}:\d{2})', input_text)
    if timestamp_match:
        metadata.timestamp = timestamp_match.group(1)
    
    # Determine action type
    if any(word in input_text.lower() for word in ["process", "index", "add", "store"]):
        metadata.action = "process"
    elif any(word in input_text.lower() for word in ["search", "find", "look for", "query"]):
        metadata.action = "search"
    
    return metadata

def extract_perception(user_input: str, url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, request_context: Optional[RequestContext] = None) -> Perception:
    """Extract perception from user input and context."""
    try:
        # Create perception with generic tool hint
        perception = Perception(
            user_input=user_input,
            url=url,
            metadata=metadata,
            tool_hint="search_tool"  # Generic tool name
        )
        
        if request_context:
            request_context.log_stage_time("perception_extraction")
            
        return perception
        
    except Exception as e:
        if request_context:
            request_context.log_stage_time("perception_error")
        raise ValueError(f"Error extracting perception: {str(e)}")
