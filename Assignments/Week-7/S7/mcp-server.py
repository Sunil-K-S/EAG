from mcp.server.fastmcp import FastMCP
from youtube_tool import YouTubeTool, YouTubeVideoInput, YouTubeVideoOutput
import asyncio
import json
from typing import Dict, Any, Optional, List
from mcp.types import TextContent
import sys
from rich.console import Console
from pydantic import BaseModel, Field, HttpUrl, validator
from enum import Enum
import time
import traceback

console = Console()
mcp = FastMCP("YouTubeAgent")

class ResponseStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"

class BaseResponse(BaseModel):
    status: ResponseStatus
    message: str
    timestamp: float = Field(default_factory=time.time)
    error_details: Optional[Dict[str, Any]] = None

class ProcessVideoInput(BaseModel):
    """Input schema for processing a YouTube video"""
    url: HttpUrl = Field(..., description="The YouTube video URL to process")

    @validator('url')
    def validate_youtube_url(cls, v):
        if 'youtube.com' not in str(v) and 'youtu.be' not in str(v):
            raise ValueError('URL must be a valid YouTube URL')
        return v

class ProcessVideoOutput(BaseResponse):
    """Output schema for video processing"""
    chunks_processed: int = Field(..., description="Number of chunks processed from the video")
    video_id: Optional[str] = None
    processing_time: Optional[float] = None

class SearchVideoInput(BaseModel):
    """Input schema for searching within a YouTube video"""
    url: HttpUrl = Field(..., description="The YouTube video URL to search in")
    query: str = Field(..., description="The search query to look for in the video")

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Search query cannot be empty')
        if len(v) > 500:
            raise ValueError('Search query too long (max 500 characters)')
        return v.strip()

class SearchResult(BaseModel):
    timestamp: str
    start: float
    content: str
    score: float

class SearchVideoOutput(BaseResponse):
    """Output schema for video search"""
    results: List[SearchResult] = Field(default_factory=list)
    total_results: int = 0
    query_time: Optional[float] = None

class YouTubeMCPTool:
    def __init__(self):
        self.youtube_tool = YouTubeTool()
        self.MAX_RETRIES = 3

    async def process_video(self, url: str) -> ProcessVideoOutput:
        start_time = time.time()
        error_details = None
        
        try:
            result = await self.youtube_tool.process_video(url)
            processing_time = time.time() - start_time
            
            if result.status == "error":
                return ProcessVideoOutput(
                    status=ResponseStatus.ERROR,
                    message=result.message,
                    chunks_processed=0,
                    processing_time=processing_time,
                    error_details={"raw_error": str(result.message)}
                )
            
            # Extract video ID from URL
            video_id = None
            try:
                video_id = self.youtube_tool._extract_video_id(url)
            except:
                pass
                
            return ProcessVideoOutput(
                status=ResponseStatus.SUCCESS,
                message=result.message,
                chunks_processed=result.data.get("chunks_processed", 0),
                video_id=video_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            error_details = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            return ProcessVideoOutput(
                status=ResponseStatus.ERROR,
                message=f"Failed to process video: {str(e)}",
                chunks_processed=0,
                processing_time=time.time() - start_time,
                error_details=error_details
            )

    async def search_video(self, query: str, url: str) -> SearchVideoOutput:
        start_time = time.time()
        error_details = None
        
        try:
            result = await self.youtube_tool.search_video(query, url)
            query_time = time.time() - start_time
            
            if result.status == "error":
                return SearchVideoOutput(
                    status=ResponseStatus.ERROR,
                    message=result.message,
                    results=[],
                    total_results=0,
                    query_time=query_time,
                    error_details={"raw_error": str(result.message)}
                )
            
            # Format results
            formatted_results = []
            if result.data and "results" in result.data:
                for r in result.data["results"]:
                    try:
                        formatted_results.append(SearchResult(
                            timestamp=r.get("timestamp", "00:00"),
                            start=float(r.get("start", 0)),
                            content=r.get("content", "").strip(),
                            score=float(r.get("score", 0.0))
                        ))
                    except Exception as e:
                        console.print(f"[yellow]Warning: Failed to format result: {e}[/yellow]")
                        continue

            return SearchVideoOutput(
                status=ResponseStatus.SUCCESS,
                message=result.message,
                results=formatted_results,
                total_results=len(formatted_results),
                query_time=query_time
            )
            
        except Exception as e:
            error_details = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            return SearchVideoOutput(
                status=ResponseStatus.ERROR,
                message=f"Failed to search video: {str(e)}",
                results=[],
                total_results=0,
                query_time=time.time() - start_time,
                error_details=error_details
            )

@mcp.tool()
async def process_video_tool(input_data: ProcessVideoInput) -> TextContent:
    """Process a YouTube video to extract and index its content
    
    This tool takes a YouTube URL and processes the video to extract its content,
    breaking it into chunks and indexing them for later search.
    """
    try:
        console.print("[blue]FUNCTION CALL:[/blue] process_video_tool()")
        console.print(f"[blue]URL:[/blue] {input_data.url}")
        
        tool = YouTubeMCPTool()
        result = await tool.process_video(str(input_data.url))

        console.print(f"[{'green' if result.status == ResponseStatus.SUCCESS else 'red'}]Process result: {result.dict()}[/{'green' if result.status == ResponseStatus.SUCCESS else 'red'}]")
        return TextContent(
            type="text",
            text=result.json()
        )
    except Exception as e:
        error_output = ProcessVideoOutput(
            status=ResponseStatus.ERROR,
            message=str(e),
            chunks_processed=0,
            error_details={
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
        console.print(f"[red]Error in process_video_tool: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=error_output.json()
        )

@mcp.tool()
async def search_video_tool(input_data: SearchVideoInput) -> TextContent:
    """Search for content within a YouTube video
    
    This tool searches for specific content within a previously processed YouTube video.
    It requires both the video URL and the search query.
    """
    try:
        console.print("[blue]FUNCTION CALL:[/blue] search_video_tool()")
        console.print(f"[blue]Query:[/blue] {input_data.query}")
        console.print(f"[blue]URL:[/blue] {input_data.url}")
        
        tool = YouTubeMCPTool()
        result = await tool.search_video(input_data.query, str(input_data.url))

        console.print(f"[{'green' if result.status == ResponseStatus.SUCCESS else 'red'}]Search result: {result.dict()}[/{'green' if result.status == ResponseStatus.SUCCESS else 'red'}]")
        return TextContent(
            type="text",
            text=result.json()
        )
    except Exception as e:
        error_output = SearchVideoOutput(
            status=ResponseStatus.ERROR,
            message=str(e),
            results=[],
            total_results=0,
            error_details={
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
        console.print(f"[red]Error in search_video_tool: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=error_output.json()
        )

if __name__ == "__main__":
    console.print("[green]Starting YouTube MCP Server...[/green]")
    # Check if running with mcp dev command
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        console.print("[yellow]Running in dev mode[/yellow]")
        mcp.run()  # Run without transport for dev server
    else:
        console.print("[yellow]Running in stdio mode[/yellow]")
        mcp.run(transport="stdio")  # Run with stdio for direct execution 