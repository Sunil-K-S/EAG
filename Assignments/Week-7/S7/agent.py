import asyncio
import time
import os
import datetime
from perception import extract_perception
from memory import MemoryManager, MemoryItem
from decision import generate_plan
from action import execute_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from youtube_tool import YouTubeTool, YouTubeVideoInput, YouTubeVideoOutput
import shutil
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize memory manager and YouTube tool
memory_manager = MemoryManager()
youtube_tool = YouTubeTool()

async def execute_plan(plan: str, memory_manager: MemoryManager, url: str = None) -> dict:
    """Execute the generated plan using available tools"""
    try:
        print(f"[execute_plan] Received plan: {plan}")
        print(f"[execute_plan] URL: {url}")
        
        # Check if plan contains a function call
        if "FUNCTION_CALL:" in plan:
            # Extract function name and arguments
            function_part = plan.split("FUNCTION_CALL:")[1].strip()
            function_name = function_part.split("|")[0].strip()
            args_str = function_part.split("|")[1].strip()
            
            print(f"[execute_plan] Function call: {function_name} with args: {args_str}")
            
            # Parse arguments
            args = {}
            for arg in args_str.split(","):
                key, value = arg.split("=")
                args[key.strip('"')] = value.strip('"')
            
            print(f"[execute_plan] Parsed args: {args}")
            
            # Execute the appropriate function
            if function_name == "search_documents":
                # Use YouTube tool for search
                print(f"[execute_plan] Calling youtube_tool.search_video with query: {args['query']} and url: {url}")
                result = await youtube_tool.search_video(args["query"], url)
                print(f"[execute_plan] Search result: {result}")
                return {
                    "status": result.status,
                    "message": result.message,
                    "data": result.data
                }
            else:
                print(f"[execute_plan] Unknown function: {function_name}")
                return {
                    "status": "error",
                    "message": f"Unknown function: {function_name}"
                }
        else:
            print(f"[execute_plan] No function call found in plan")
            return {
                "status": "success",
                "message": plan,
                "data": None
            }
    except Exception as e:
        print(f"[execute_plan] Error: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

class AgentRequest(BaseModel):
    user_input: str
    url: str
    intent: Optional[str] = "search"
    entities: Optional[List[str]] = []
    tool_hint: Optional[str] = None

class AgentResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

@app.post("/agent")
async def process_request(request: AgentRequest) -> AgentResponse:
    try:
        print(f"[process_request] Received request: {request}")
        
        # Extract perception
        perception = extract_perception(request.user_input)
        print(f"[process_request] Extracted perception: {perception}")
        
        # Get relevant memories
        memory_items = memory_manager.retrieve(request.user_input)
        print(f"[process_request] Retrieved memories: {len(memory_items)} items")
        
        # Generate plan with memory items
        plan = generate_plan(perception, memory_items)
        print(f"[process_request] Generated plan: {plan}")
        
        # Execute plan with URL
        result = await execute_plan(plan, memory_manager, request.url)
        print(f"[process_request] Execution result: {result}")
        
        return AgentResponse(
            status="success",
            message="Request processed successfully",
            data=result
        )
    except Exception as e:
        print(f"[process_request] Error: {str(e)}")
        return AgentResponse(
            status="error",
            message=str(e)
        )

def run_agent():
    """Run the agent in interactive mode"""
    memory_manager = MemoryManager()
    
    print("🧑 What do you want to solve today? → ", end="")
    while True:
        try:
            user_input = input().strip()
            if not user_input:
                continue
                
            # Extract perception
            perception = extract_perception(user_input)
            
            # Get relevant memories
            memory_items = memory_manager.retrieve(user_input)
            
            # Generate plan
            plan = generate_plan(perception, memory_items)
            
            # Execute plan
            result = execute_plan(plan, memory_manager)
            
            # Store result in memory
            memory_item = MemoryItem(
                text=user_input,
                type="interaction",
                metadata={"result": str(result)}
            )
            memory_manager.add(memory_item)
            
            print("🧑 What do you want to solve today? → ", end="")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("🧑 What do you want to solve today? → ", end="")

if __name__ == "__main__":
    # Check if running as server or interactive mode
    if os.getenv("RUN_AS_SERVER", "false").lower() == "true":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        run_agent()


# Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
# How much Anmol singh paid for his DLF apartment via Capbridge? 
# What do you know about Don Tapscott and Anthony Williams?
# What is the relationship between Gensol and Go-Auto?