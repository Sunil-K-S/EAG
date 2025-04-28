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

    def make_decision(self, perception: Perception, memories: List[MemoryItem], tool_descriptions: str = None) -> str:
        """Generate a plan based on perception and memories."""
        try:
            # Check if this is a YouTube video request
            if perception.url and "youtube.com" in perception.url:
                # Extract video ID
                video_id = perception.url.split("v=")[1].split("&")[0]
                
                # Check if video is already processed
                video_processed = any(
                    item.type == "youtube_chunk" and 
                    any(tag == video_id for tag in item.tags)
                    for item in memories
                )
                
                if not video_processed:
                    # Need to process the video first
                    log("decision", "Video not processed, will process first")
                    return (
                        f"FUNCTION_CALL: process_video_tool|"
                        f"input_data={{"
                        f"'input_data': {{"
                        f"'url': '{perception.url}',"
                        f"'action': 'process'"
                        f"}}}}"
                    )
                else:
                    # Video is processed, can search directly
                    log("decision", "Video already processed, searching directly")
                    return (
                        f"FUNCTION_CALL: search_video_tool|"
                        f"input_data={{"
                        f"'input_data': {{"
                        f"'url': '{perception.url}',"
                        f"'query': '{perception.user_input}',"
                        f"'action': 'search'"
                        f"}}}}"
                    )
            
            # For non-YouTube requests, use standard planning
            return self.generate_plan(perception, memories, tool_descriptions)
            
        except Exception as e:
            log("decision", f"Error in decision making: {str(e)}")
            return f"FINAL_ANSWER: Error in decision making: {str(e)}"

    def prepare_prompt(self, perception: Perception, memories: List[MemoryItem], tool_descriptions: str) -> str:
        """Prepare the current prompt with history and next step guidance."""
        # Format history with step numbers and results
        history_text = "\n".join(
            f"Step {i+1}: {item.get('function', 'Unknown function')} - {item.get('message', 'No message available')}"
            for i, item in enumerate(self.history)
        )
        
        # Add next step guidance based on history
        next_step_guidance = "\nWhat should I do next?" if self.history else "\nWhat should I do first?"
        
        # Format memory items
        memory_texts = "\n".join(f"- {m.text}" for m in memories) or "None"
        
        # For YouTube URLs, check if video is already processed
        video_status = ""
        if perception.url and "youtube.com" in perception.url:
            video_id = perception.url.split("v=")[1].split("&")[0]
            processed = any(
                item.type == "youtube_chunk" and 
                any(tag == video_id for tag in item.tags)
                for item in memories
            )
            video_status = f"""
Video Processing Status:
- Video ID: {video_id}
- Status: {'Already processed' if processed else 'Needs processing'}
"""

        # Generate tool rules from available tools
        tool_rules = []
        for tool_desc in tool_descriptions.split('\n\n'):
            if not tool_desc.strip():
                continue
            tool_name = tool_desc.split(':')[0].strip('- ')
            tool_rules.append(f"- {tool_desc}")

        return f"""
        You are a reasoning-driven AI agent with access to tools. Your job is to solve the user's request step-by-step by reasoning through the problem, selecting a tool if needed, and continuing until the FINAL_ANSWER is produced.

        Available Tools and Their Usage:
        {tool_descriptions}

        Tool Rules:
        {self.tool_rules}

        History of completed steps:
        {history_text}

        Relevant memories:
        {memory_texts}

        Current Context:
        - User input: "{perception.user_input}"
        - URL: {perception.url or 'None'}
        - Tool hint: {perception.tool_hint or 'None'}
        {video_status}

        IMPORTANT OUTPUT FORMAT RULES:
        1. You must respond with EXACTLY ONE line containing either:
           - FUNCTION_CALL: tool_name|input_data={'input_data': {'param1': 'value1', 'param2': 'value2'}}
           - FINAL_ANSWER: [your answer]
        2. DO NOT include any explanations, reasoning, or additional text
        3. DO NOT use multiple lines
        4. DO NOT include any formatting or markdown
        5. DO NOT include any examples or suggestions

        Guidelines:
        - Use only the tools listed above
        - Follow the tool descriptions for proper usage
        - If the previous tool output already contains factual information, DO NOT search again
        - DO NOT repeat function calls with the same parameters
        - If unsure or no tool fits, respond with: FINAL_ANSWER: [unknown]
        - You have only 3 attempts. Final attempt must be FINAL_ANSWER
        {next_step_guidance}
        """

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
