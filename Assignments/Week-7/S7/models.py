from pydantic import BaseModel, Field, validator, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum
import re

# Input/Output models for tools

class AddInput(BaseModel):
    a: int
    b: int

class AddOutput(BaseModel):
    result: int

class SqrtInput(BaseModel):
    a: int

class SqrtOutput(BaseModel):
    result: float

class StringsToIntsInput(BaseModel):
    string: str

class StringsToIntsOutput(BaseModel):
    ascii_values: List[int]

class ExpSumInput(BaseModel):
    int_list: List[int]

class ExpSumOutput(BaseModel):
    result: float

class ActionType(Enum):
    PROCESS = "process"
    SEARCH = "search"
    UNKNOWN = "unknown"

class ResponseStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"

class BaseResponse(BaseModel):
    status: ResponseStatus
    message: str
    error_details: Optional[Dict[str, Any]] = None

class YouTubeMetadata(BaseModel):
    video_id: str = Field(..., description="YouTube video ID")
    timestamp: Optional[str] = Field(None, description="Timestamp in video (MM:SS or HH:MM:SS)")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    title: Optional[str] = Field(None, description="Video title")
    channel: Optional[str] = Field(None, description="Channel name")
    action: ActionType = Field(default=ActionType.UNKNOWN)

    @validator('timestamp')
    def validate_timestamp(cls, v):
        if v is not None:
            if not re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', v):
                raise ValueError('Invalid timestamp format')
        return v

    @validator('duration')
    def validate_duration(cls, v):
        if v is not None:
            if v < 0 or v > 86400:  # Max 24 hours
                raise ValueError('Duration must be between 0 and 86400 seconds')
        return v

class SearchResult(BaseModel):
    text: str = Field(..., description="The text content of the result")
    timestamp: str = Field(..., description="Timestamp in video (MM:SS)")
    start: float = Field(..., description="Start time in seconds")
    duration: Optional[float] = Field(None, description="Duration of the segment in seconds")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")

    @validator('timestamp')
    def validate_timestamp(cls, v):
        if not re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', v):
            raise ValueError('Invalid timestamp format')
        return v

    @validator('start')
    def validate_start(cls, v):
        if v < 0 or v > 86400:  # Max 24 hours
            raise ValueError('Start time must be between 0 and 86400 seconds')
        return v

    @validator('duration')
    def validate_duration(cls, v):
        if v is not None:
            if v <= 0 or v > 3600:  # Max 1 hour
                raise ValueError('Duration must be between 0 and 3600 seconds')
        return v

class ProcessVideoInput(BaseModel):
    url: HttpUrl = Field(..., description="The YouTube video URL to process")
    metadata: Optional[YouTubeMetadata] = None

    @validator('url')
    def validate_youtube_url(cls, v):
        if 'youtube.com' not in str(v) and 'youtu.be' not in str(v):
            raise ValueError('URL must be a valid YouTube URL')
        return v

class ProcessVideoOutput(BaseResponse):
    chunks_processed: int = Field(..., ge=0, description="Number of chunks processed")
    video_id: str = Field(..., description="YouTube video ID")
    metadata: Optional[YouTubeMetadata] = None
    processing_time: Optional[float] = None

class SearchVideoInput(BaseModel):
    url: HttpUrl = Field(..., description="The YouTube video URL to search in")
    query: str = Field(..., min_length=1, max_length=500, description="The search query")
    metadata: Optional[YouTubeMetadata] = None

    @validator('url')
    def validate_youtube_url(cls, v):
        if 'youtube.com' not in str(v) and 'youtu.be' not in str(v):
            raise ValueError('URL must be a valid YouTube URL')
        return v

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Search query cannot be empty')
        return v.strip()

class SearchVideoOutput(BaseResponse):
    results: List[SearchResult] = Field(default_factory=list)
    total_results: int = Field(..., ge=0)
    query_time: Optional[float] = None
    metadata: Optional[YouTubeMetadata] = None
