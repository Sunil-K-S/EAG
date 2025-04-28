from typing import Dict, Any, Union, Tuple
from pydantic import BaseModel
from mcp import ClientSession
import ast
import time
import json
from memory import MemoryManager, MemoryItem
from request_types import RequestContext
from mcp.client.stdio import StdioServerParameters, stdio_client
from enum import Enum

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str, request_context: RequestContext = None):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")

class ResultStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"

class ToolCallResult(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Union[str, list, dict]
    raw_response: Any
    status: ResultStatus = ResultStatus.SUCCESS

def parse_function_call(response: str) -> tuple[str, Dict[str, Any]]:
    """Parses FUNCTION_CALL string into tool name and arguments."""
    try:
        if not response.startswith("FUNCTION_CALL:"):
            raise ValueError("Not a valid FUNCTION_CALL")

        _, function_info = response.split(":", 1)
        parts = [p.strip() for p in function_info.split("|")]
        func_name, param_parts = parts[0], parts[1:]

        result = {}
        for part in param_parts:
            if "=" not in part:
                raise ValueError(f"Invalid param: {part}")
            key, value = part.split("=", 1)

            try:
                parsed_value = ast.literal_eval(value)
            except Exception:
                parsed_value = value.strip()

            # Handle nested keys
            keys = key.split(".")
            current = result
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = parsed_value

        log("parser", f"Parsed: {func_name} → {result}")
        return func_name, result

    except Exception as e:
        log("parser", f"❌ Failed to parse FUNCTION_CALL: {e}")
        raise

async def execute_tool(session: ClientSession, tool_name: str, arguments: Dict[str, Any], max_retries: int = 3) -> ToolCallResult:
    """Executes a tool via MCP session with retries."""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            log("tool", f"⚙️ Attempt {attempt + 1}/{max_retries}: Calling '{tool_name}' with: {arguments}")
            
            # Format arguments as input_data for the tool
            input_data = arguments.get('input_data', {})
            if not input_data:
                # If input_data is not present, assume all arguments should be nested
                input_data = {"input_data": arguments}
            
            result = await session.call_tool(tool_name, arguments=input_data)

            if hasattr(result, 'content'):
                if isinstance(result.content, list):
                    out = [getattr(item, 'text', str(item)) for item in result.content]
                else:
                    out = getattr(result.content, 'text', str(result.content))
            else:
                out = str(result)

            # Try to parse the result as JSON
            try:
                if isinstance(out, str):
                    parsed_out = json.loads(out)
                    # Check for error indicators in the response
                    if isinstance(parsed_out, dict):
                        if parsed_out.get('status') == 'error' or 'error' in parsed_out:
                            raise Exception(parsed_out.get('message', str(parsed_out)))
                    out = parsed_out
            except json.JSONDecodeError:
                pass  # Not JSON, use as is

            log("tool", f"✅ {tool_name} result: {out}")
            
            # For process_video_tool, if successful, immediately follow with search
            if (tool_name == 'process_video_tool' and 
                isinstance(out, dict) and 
                out.get('status') == 'success'):
                # Extract query from arguments if it exists
                query = arguments.get('query', '')
                if query:
                    log("tool", f"Video processed successfully, proceeding to search for: {query}")
                    search_result = await execute_tool(
                        session,
                        'search_video_tool',
                        {
                            'input_data': {
                                'url': arguments['input_data']['url'],
                                'query': query,
                                'action': 'search'
                            }
                        },
                        max_retries
                    )
                    if search_result.status == ResultStatus.SUCCESS:
                        return search_result
            
            return ToolCallResult(
                tool_name=tool_name,
                arguments=arguments,
                result=out,
                raw_response=result,
                status=ResultStatus.SUCCESS
            )

        except Exception as e:
            last_error = e
            log("tool", f"⚠️ Attempt {attempt + 1} failed for '{tool_name}': {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            break

    log("tool", f"❌ All attempts failed for '{tool_name}': {last_error}")
    return ToolCallResult(
        tool_name=tool_name,
        arguments=arguments,
        result=str(last_error),
        raw_response=None,
        status=ResultStatus.FAILURE
    )

class ActionLayer:
    """Layer responsible for executing actions and tools."""
    
    def __init__(self):
        self.MAX_RETRIES = 3
        
    async def execute_plan(self, plan: str, memory_manager: MemoryManager, request_context: RequestContext = None, session: ClientSession = None) -> str:
        """Execute a plan using available tools."""
        try:
            log("action", f"Executing plan: {plan}", request_context)
            
            if not session:
                raise ValueError("No MCP session provided")
                    
            if "FUNCTION_CALL:" in plan:
                function_name, arguments = parse_function_call(plan)
                result = await execute_tool(session, function_name, arguments, self.MAX_RETRIES)
                
                # Store the result in memory with appropriate type
                memory_type = "youtube_chunk" if function_name == "search_tool" and arguments.get("action") == "process" else "tool_output"
                
                memory_item = MemoryItem(
                    text=str(result.result),
                    type=memory_type,
                    metadata={
                        "tool": function_name,
                        "arguments": arguments,
                        "timestamp": time.time(),
                        "status": result.status.value
                    }
                )
                memory_manager.add(memory_item)
                
                # Format the response based on the action type and status
                if result.status == ResultStatus.FAILURE:
                    return f"Error: {result.result}"
                
                if isinstance(result.result, dict):
                    if "status" in result.result and "message" in result.result:
                        if "data" in result.result and "results" in result.result["data"]:
                            # Format search results
                            results = result.result["data"]["results"]
                            formatted_results = []
                            for idx, item in enumerate(results, 1):
                                formatted_results.append(
                                    f"\nResult {idx} (at {item['timestamp']}):\n"
                                    f"Text: {item['text']}\n"
                                    f"Score: {item['score']}"
                                )
                            return f"{result.result['message']}\n{''.join(formatted_results)}"
                        return f"{result.result['message']}\nStatus: {result.result['status']}"
                    return json.dumps(result.result, indent=2)
                elif isinstance(result.result, list):
                    return "\n".join(str(item) for item in result.result)
                else:
                    return str(result.result)
            else:
                return plan
                
        except Exception as e:
            log("error", f"Error executing plan: {str(e)}", request_context)
            return f"Error executing plan: {str(e)}"
