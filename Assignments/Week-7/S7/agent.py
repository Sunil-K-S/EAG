import asyncio
import time
import os
import datetime
import uuid
import json
from typing import Dict, Any
from perception import extract_perception, Perception
from memory import MemoryManager, MemoryItem
from decision import DecisionLayer
from action import ActionLayer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import shutil
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
from dotenv import load_dotenv
from request_types import RequestContext
from rich.console import Console

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

# Initialize components
console = Console()
decision_layer = DecisionLayer()
memory_manager = MemoryManager()
action_layer = ActionLayer()

def log(stage: str, msg: str, request_context: RequestContext = None):
    """Helper function for consistent logging"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    request_id = f"[{request_context.request_id}] " if request_context else ""
    duration = f" (took {request_context.stage_times.get(stage, 0):.2f}s)" if request_context else ""
    console.print(f"[{now}] {request_id}[{stage}]{duration} {msg}")

def format_search_result(result: dict) -> str:
    """Format search result for better readability"""
    if not result:
        return "No results"
    formatted = []
    for idx, item in enumerate(result.get('results', [])):
        formatted.append(f"\nResult {idx + 1} (at {item['timestamp']}):")
        formatted.append(f"Text: {item['text'][:100]}...")
        formatted.append(f"Score: {item['score']}")
        if 'start' in item:
            formatted.append(f"Start time: {item['start']}s")
    return "\n".join(formatted)

async def execute_plan(plan: str, memory_manager: MemoryManager, url: str = None, request_context: RequestContext = None) -> str:
    """Execute the generated plan using available tools"""
    try:
        log("plan", f"Starting plan execution: {plan}", request_context)
        log("plan", f"URL context: {url}", request_context)
        
        # If URL is provided, add it to the plan
        if url and "FUNCTION_CALL:" in plan:
            function_part = plan.split("FUNCTION_CALL:")[1].strip()
            function_name = function_part.split("|")[0].strip()
            
            # Add URL parameter if it's a search function
            if function_name == "search_documents":
                plan = f"FUNCTION_CALL:{function_name}|url={url}|{function_part.split('|', 1)[1]}"
                log("plan", f"Updated plan with URL: {plan}", request_context)
        
        # Initialize MCP connection
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                log("mcp", "MCP connection established", request_context)
                
                # Execute plan using the action layer
                result = await action_layer.execute_plan(plan, memory_manager, request_context, session)
                return result
            
    except Exception as e:
        log("error", f"Plan execution failed: {str(e)}", request_context)
        return str(e)

class Request(BaseModel):
    user_input: str
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Response(BaseModel):
    result: str
    metadata: Optional[Dict[str, Any]] = None

@app.post("/agent", response_model=Response)
async def process_request(request: Request):
    """Process a user request through the agent's layers."""
    try:
        # Create request context for tracking
        request_context = RequestContext()
        request_context.log_stage_time("start")
        
        # Initialize MCP connection to get available tools
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                log("mcp", "MCP connection established", request_context)
                
                # Get available tools
                tools_result = await session.list_tools()
                tools = tools_result.tools
                tool_descriptions = "\n".join(
                    f"- {tool.name}: {getattr(tool, 'description', 'No description')}" 
                    for tool in tools
                )
                log("mcp", f"Available tools: {tool_descriptions}", request_context)
                
                # Extract perception
                log("agent", "Extracting perception...", request_context)
                perception = extract_perception(request.user_input, request.url, request.metadata, request_context)
                request_context.log_stage_time("perception")
                
                # Retrieve relevant memories
                log("agent", "Retrieving memories...", request_context)
                memories = memory_manager.retrieve(perception.user_input, top_k=3)
                request_context.log_stage_time("memory")
                
                # Generate plan
                log("agent", "Generating plan...", request_context)
                plan = decision_layer.make_decision(perception, memories, tool_descriptions)
                request_context.log_stage_time("planning")
                
                # Execute plan
                log("agent", "Executing plan...", request_context)
                result = await execute_plan(plan, memory_manager, request.url, request_context)
                request_context.log_stage_time("execution")
                
                # Calculate total time
                total_time = request_context.calculate_total_time()
                log("agent", f"Request completed in {total_time:.2f}s", request_context)
                
                return Response(
                    result=result,
                    metadata={
                        "total_time": total_time,
                        "stages": request_context.stage_times
                    }
                )
                
    except Exception as e:
        log("agent", f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
            log("perception", f"Extracted perception: {perception}")
            
            # Get relevant memories
            memory_items = memory_manager.retrieve(user_input)
            log("memory", f"Retrieved {len(memory_items)} relevant memories")
            
            # Generate plan
            plan = decision_layer.make_decision(perception, memory_items)
            log("plan", f"Generated plan: {plan}")
            
            # Execute plan
            result = execute_plan(plan, memory_manager)
            log("execution", f"Plan execution completed: {result}")
            
            # Store result in memory
            memory_item = MemoryItem(
                text=user_input,
                type="interaction",
                metadata={"result": str(result)}
            )
            memory_manager.add(memory_item)
            log("memory", "Stored interaction in memory")
            
            print("🧑 What do you want to solve today? → ", end="")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            log("error", f"Error in interactive mode: {e}")
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