from pydantic import BaseModel
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
import json

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")

load_dotenv()

# Configure the API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class YouTubeMetadata(BaseModel):
    video_id: Optional[str] = None
    timestamp: Optional[str] = None
    action: Optional[str] = None  # "process" or "search"

class PerceptionResult(BaseModel):
    user_input: str
    intent: str
    entities: List[str]
    tool_hint: Optional[str] = None
    youtube_metadata: Optional[YouTubeMetadata] = None

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

def extract_perception(user_input: str) -> PerceptionResult:
    """Extracts intent, entities, and tool hints using LLM"""
    try:
        # First extract YouTube-specific metadata
        youtube_metadata = extract_youtube_metadata(user_input)

        prompt = f"""
        You are an AI that extracts structured facts from user input, with special attention to YouTube-related queries.

        Input: "{user_input}"

        Return the response as a JSON object with keys:
        - intent: (brief phrase about what the user wants, including if it's YouTube-related)
        - entities: a list of strings representing keywords or values
        - tool_hint: (name of the MCP tool that might be useful, if any)

        For YouTube queries, consider:
        - Is this about processing a video?
        - Is this about searching within a video?
        - What specific content is being requested?

        Output only the JSON object. Do NOT include any other text or formatting.
        """

        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        raw = response.text.strip()
        log("perception", f"LLM output: {raw}")

        # Clean the output by removing markdown code blocks if present
        cleaned_output = raw.strip()
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output[7:]
        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output[:-3]
        cleaned_output = cleaned_output.strip()
        
        # Parse the JSON output
        parsed = json.loads(cleaned_output)
        
        # Convert null to None for Python
        if parsed.get("tool_hint") == "null":
            parsed["tool_hint"] = None

        # Fix common issues
        if isinstance(parsed.get("entities"), dict):
            parsed["entities"] = list(parsed["entities"].values())

        # Add YouTube metadata if relevant
        if youtube_metadata.video_id or youtube_metadata.action:
            parsed["youtube_metadata"] = youtube_metadata

        return PerceptionResult(user_input=user_input, **parsed)
        
    except Exception as e:
        log("perception", f"⚠️ Extraction failed: {e}")
        # Return a default perception result
        return PerceptionResult(
            user_input=user_input,
            intent="search",
            entities=[user_input],
            tool_hint="youtube_tool"
        )
