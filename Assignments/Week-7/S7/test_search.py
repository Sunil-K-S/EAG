import asyncio
from youtube_tool import YouTubeTool
import json

async def test_search():
    # Initialize the tool
    tool = YouTubeTool()
    
    # Test video URL
    url = "https://www.youtube.com/watch?v=Xh57mMlfuMk"
    
    # First, process the video
    print("Processing video...")
    process_result = await tool.process_video(url)
    print(f"Process result: {json.dumps(process_result.model_dump(), indent=2)}")
    
    # Then search
    print("\nSearching video...")
    search_result = await tool.search_video("What is the main topic of this video?", url)
    print(f"Search result: {json.dumps(search_result.model_dump(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_search()) 