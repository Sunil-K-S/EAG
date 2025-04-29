from typing import List, Optional, Dict
from pydantic import BaseModel
from memory import MemoryItem
from perception import Perception
from request_types import RequestContext
import time
import json
from dotenv import load_dotenv
import google.generativeai as genai
import os

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str, request_context: RequestContext = None):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")

# Load environment variables
load_dotenv()

# Configure the API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class DecisionLayer:
    def __init__(self):
        self.history = []
        self.iteration = 0
        self.MAX_ITERATIONS = 6
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize tool rules memory
        self.tool_rules = """
        1. For YouTube videos:
           - If video is not processed, use process_video_tool first
           - If video is already processed, use search_video_tool
           - Never reprocess a video that's already in the index
        2. For all tools:
           - Use only the tools listed in Available Tools
           - Follow the tool's description for required parameters
           - Check tool output before making next decision
        """

    def make_decision(self, perception: Perception, memories: List[MemoryItem], tool_descriptions: str) -> str:
        """Make a decision based on the perception and memories."""
        try:
            # Prepare context for LLM
            context = {
                "user_input": perception.user_input,
                "url": perception.url,
                "tool_hint": perception.tool_hint,
                "available_tools": tool_descriptions,
                "memories": [memory.text for memory in memories]
            }
            
            # Generate prompt
            prompt = self.prepare_prompt(context)
            
            # Get LLM response
            response = self.model.generate_content(prompt)
            
            # Validate and parse the plan
            plan = self.validate_plan(response.text.strip())
            
            # If plan is invalid, generate a default plan
            if not plan:
                if perception.tool_hint == "search_video_tool":
                    # For search requests, directly use search_video_tool
                    plan = f"FUNCTION_CALL:search_video_tool|input_data={{'input_data': {{'url': '{perception.url}', 'query': '{perception.user_input}', 'action': 'search'}}}}"
                else:
                    # For other requests, check if video needs processing
                    if perception.url and "youtube.com" in perception.url:
                        video_id = perception.url.split("v=")[1].split("&")[0]
                        if not any(f"youtube_chunk_{video_id}" in memory.text for memory in memories):
                            plan = f"FUNCTION_CALL:process_video_tool|input_data={{'input_data': {{'url': '{perception.url}', 'action': 'process'}}}}"
                        else:
                            plan = f"FUNCTION_CALL:search_video_tool|input_data={{'input_data': {{'url': '{perception.url}', 'query': '{perception.user_input}', 'action': 'search'}}}}"
                    else:
                        plan = f"FUNCTION_CALL:search_documents|input_data={{'input_data': {{'query': '{perception.user_input}'}}}}"
            
            return plan
            
        except Exception as e:
            log("decision", f"Error in decision making: {str(e)}")
            # Return a default plan in case of error
            if perception.tool_hint == "search_video_tool":
                return f"FUNCTION_CALL:search_video_tool|input_data={{'input_data': {{'url': '{perception.url}', 'query': '{perception.user_input}', 'action': 'search'}}}}"
            return f"FUNCTION_CALL:search_documents|input_data={{'input_data': {{'query': '{perception.user_input}'}}}}"

    def prepare_prompt(self, context: dict) -> str:
        """Prepare the prompt for the LLM."""
        return f"""You are an AI assistant that helps users find information. Based on the following context, generate a plan to help the user.

Context:
- User Input: {context['user_input']}
- URL: {context['url']}
- Tool Hint: {context['tool_hint']}
- Available Tools:
{context['available_tools']}
- Recent Memories:
{chr(10).join(context['memories'])}

Rules:
1. If the user is searching within a YouTube video:
   - First check if the video has been processed (look for 'youtube_chunk_' in memories)
   - If not processed, use process_video_tool
   - If processed, use search_video_tool
2. For search_video_tool, include both URL and query
3. For process_video_tool, only include URL
4. Format must be: FUNCTION_CALL:tool_name|input_data={{'input_data': {{...}}}}

Generate a plan following these rules."""

    def validate_plan(self, plan: str) -> str:
        """Validate the generated plan."""
        try:
            # Check if plan starts with FUNCTION_CALL:
            if not plan.startswith("FUNCTION_CALL:"):
                return None
                
            # Split into tool and input_data
            parts = plan.split("|", 1)
            if len(parts) != 2:
                return None
                
            tool_name = parts[0].replace("FUNCTION_CALL:", "").strip()
            input_data = parts[1].strip()
            
            # Validate tool name
            if tool_name not in ["process_video_tool", "search_video_tool", "search_documents"]:
                return None
                
            # Validate input_data format
            if not input_data.startswith("input_data="):
                return None
                
            # Try to parse the input_data
            try:
                eval(input_data.replace("input_data=", ""))
            except:
                return None
                
            return plan
            
        except Exception as e:
            log("decision", f"Error validating plan: {str(e)}")
            return None

    def generate_plan(
        self,
        perception: Perception,
        memory_items: List[MemoryItem],
        tool_descriptions: Optional[str] = None,
        request_context: RequestContext = None
    ) -> str:
        """Generates a plan (tool call or final answer) using LLM based on structured perception and memory."""

        try:
            start_time = time.time()
            log("plan", f"Using {len(memory_items)} memory items for planning", request_context)
            log("plan", f"Tool context: {tool_descriptions}", request_context)

            # Check iteration limit
            if self.iteration >= self.MAX_ITERATIONS:
                return "FINAL_ANSWER: [Maximum iterations reached]"

            # Prepare prompt with history and context
            prompt = self.prepare_prompt(perception, memory_items, tool_descriptions)

            # Get LLM response using the initialized model
            response = self.model.generate_content(prompt)
            raw = response.text.strip()
            log("plan", f"LLM output: {raw}", request_context)

            # Extract function call or final answer
            for line in raw.splitlines():
                if line.strip().startswith("FUNCTION_CALL:") or line.strip().startswith("FINAL_ANSWER:"):
                    duration = time.time() - start_time
                    log("plan", f"Plan generation completed in {duration:.2f}s", request_context)
                    
                    # Store in history if it's a function call
                    if line.strip().startswith("FUNCTION_CALL:"):
                        # Parse the function call to get better metadata
                        try:
                            func_parts = line.split("|")
                            func_name = func_parts[0].split(":")[1].strip()
                            func_args = {}
                            for part in func_parts[1:]:
                                if "=" in part:
                                    key, value = part.split("=", 1)
                                    func_args[key.strip()] = value.strip()
                            
                            self.history.append({
                                'function': func_name,
                                'arguments': func_args,
                                'message': 'Step executed',
                                'timestamp': time.time()
                            })
                        except Exception as e:
                            log("plan", f"Error parsing function call: {str(e)}", request_context)
                            self.history.append({
                                'function': line,
                                'message': 'Step executed'
                            })
                        self.iteration += 1
                    
                    return line.strip()

            return raw.strip()
            
        except Exception as e:
            log("plan", f"⚠️ Decision generation failed: {str(e)}", request_context)
            return "FINAL_ANSWER: [unknown]"

    def _create_action_plan(self, tool_name: str, action: str, url: Optional[str] = None, query: Optional[str] = None) -> str:
        """Create a function call string for the action plan."""
        args = []
        if url:
            args.append(f"input_data.url={url}")
        if query:
            args.append(f"input_data.query={query}")
        args.append(f"input_data.action={action}")
        
        return f"FUNCTION_CALL: {tool_name}|{'|'.join(args)}"

    def validate_action_plan(self, plan: str) -> bool:
        """Validate that the action plan is properly formatted."""
        if plan.startswith("FINAL_ANSWER:"):
            return True
            
        if not plan.startswith("FUNCTION_CALL:"):
            return False
            
        try:
            parts = plan.split("|")
            if len(parts) < 2:
                return False
                
            # Extract tool name
            tool_name = parts[0].split(":")[1].strip()
            
            # Check if tool is available
            if self.available_tools and tool_name not in self.available_tools:
                return False
                
            # Check action
            if not any(p.startswith("input_data.action=") for p in parts[1:]):
                return False
                
            return True
            
        except Exception:
            return False
