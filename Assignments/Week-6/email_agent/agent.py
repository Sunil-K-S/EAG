import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import google.generativeai as genai
from concurrent.futures import TimeoutError
from functools import partial
import subprocess
import time
import json
from typing import Dict, List, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from .email_models import (
    VerificationType,
    ResultStatus,
    VerificationChecks,
    ReasoningInfo,
    FunctionCall,
    FinalAnswer,
    VerificationResult,
    EmailVerification,
    CalculationVerification,
    ASCIIVerification,
    ContentVerification,
    StepResult,
    LLMResponse
)

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Constants
MAX_ITERATIONS = 6
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10

# Initialize rich console
console = Console()

class EmailAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            'gemini-2.0-flash-001',
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        )
        self.iteration = 0
        self.history = []
        self.verification_results = []

    async def verify_step(self, step_result: Dict[str, Any], verification_type: VerificationType) -> Tuple[bool, str]:
        """Verify a single step result with detailed checking."""
        try:
            print(f"DEBUG: Verifying step with type: {verification_type}")
            print(f"DEBUG: Step result type: {type(step_result)}")
            print(f"DEBUG: Step result: {step_result}")

            # Extract result content based on verification type
            if verification_type == VerificationType.ASCII:
                if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                    values = [int(item.text) for item in step_result.content]
                    print(f"DEBUG: Extracted ASCII values: {values}")
                    return await self.verify_ascii(ASCIIVerification(values=values))
            elif verification_type == VerificationType.CALCULATION:
                print(f"DEBUG: Passing raw result to verify_calculation: {step_result}")
                return await self.verify_calculation(CalculationVerification(result=step_result))
            elif verification_type == VerificationType.EMAIL:
                if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                    try:
                        content_text = step_result.content[0].text
                        print(f"DEBUG: Email content text: {content_text}")
                        outer_data = json.loads(content_text)
                        print(f"DEBUG: Email outer data: {outer_data}")
                        inner_data = json.loads(outer_data['content'][0]['text'])
                        print(f"DEBUG: Email inner data: {inner_data}")
                        if inner_data.get('is_valid', False):
                            return True, "Email verification passed"
                    except (json.JSONDecodeError, IndexError, AttributeError) as e:
                        print(f"DEBUG: Email verification error: {str(e)}")
                        return False, f"Email verification error: {str(e)}"
                return False, "Invalid email result format"
            elif verification_type == VerificationType.CONTENT:
                if hasattr(step_result, 'parameters'):
                    subject = step_result.parameters.get('subject', '')
                    body = step_result.parameters.get('body', '')
                    print(f"DEBUG: Extracted content - subject: {subject}, body length: {len(body)}")
                    return await self.verify_content(ContentVerification(subject=subject, body=body))
            else:
                print(f"DEBUG: Using general verification for result: {step_result}")
                return await self.verify_general(step_result)

            return False, "Unsupported verification type or invalid result format"
        except Exception as e:
            print(f"DEBUG: Verification error: {str(e)}")
            return False, f"Verification failed: {str(e)}"

    async def verify_email(self, result: EmailVerification) -> Tuple[bool, str]:
        """Verify email-related operations."""
        try:
            # Basic format check
            if not "@" in result.email or not "." in result.email:
                return False, "Invalid email format"
                
            # Length check
            if len(result.email) > 254:  # RFC 5321
                return False, "Email too long"
                
            return True, "Email verification passed"
        except Exception as e:
            return False, f"Email verification error: {str(e)}"

    async def verify_calculation(self, result: CalculationVerification) -> Tuple[bool, str]:
        """Verify calculation results."""
        try:
            print(f"DEBUG: Starting calculation verification")
            print(f"DEBUG: Result type: {type(result)}")
            print(f"DEBUG: Raw result: {result}")

            # Handle case where result is a string
            if isinstance(result.result, str):
                try:
                    print(f"DEBUG: Parsing string result as JSON")
                    result.result = json.loads(result.result)
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {str(e)}")
                    return False, "Invalid JSON string format"

            # Extract the result from the complex response structure
            if hasattr(result.result, 'content') and isinstance(result.result.content, list):
                print(f"DEBUG: Processing content list")
                # Get the first content item's text
                content_text = result.result.content[0].text
                print(f"DEBUG: Content text: {content_text}")
                
                # Parse the outer JSON string
                outer_data = json.loads(content_text)
                print(f"DEBUG: Outer data: {outer_data}")
                
                # Parse the inner JSON string from the content array
                inner_data = json.loads(outer_data['content'][0]['text'])
                print(f"DEBUG: Inner data: {inner_data}")
                
                if inner_data.get('is_valid'):
                    result_value = inner_data['data']['result']
                    print(f"DEBUG: Extracted result value: {result_value}")
                    
                    # Validate the result
                    if isinstance(result_value, (int, float)):
                        if abs(result_value) > 1e308:  # Max float value
                            return False, "Result too large"
                        if isinstance(result_value, float) and (result_value != result_value or result_value == float('inf')):
                            return False, "Invalid numerical result"
                        return True, f"Valid calculation result: {result_value}"
                    return False, "Result is not a number"
                return False, f"Calculation validation failed: {inner_data.get('details', 'Unknown error')}"
            
            return False, "Invalid result format"
        except json.JSONDecodeError as e:
            print(f"DEBUG: JSON parsing error: {str(e)}")
            return False, f"JSON parsing error: {str(e)}"
        except Exception as e:
            print(f"DEBUG: Calculation verification error: {str(e)}")
            return False, f"Calculation verification error: {str(e)}"

    async def verify_ascii(self, result: ASCIIVerification) -> Tuple[bool, str]:
        """Verify ASCII values."""
        try:
            # Convert all values to integers
            try:
                values = [int(v) for v in result.values]
            except (ValueError, TypeError):
                return False, "Invalid ASCII value format"

            # Valid ASCII range check
            if not all(0 <= x <= 127 for x in values):
                invalid_values = [x for x in values if not (0 <= x <= 127)]
                return False, f"Invalid ASCII values found: {invalid_values}"

            print(f"DEBUG: Verified ASCII values: {values}")
            return True, f"Valid ASCII values: {values}"
        except Exception as e:
            return False, f"ASCII verification error: {str(e)}"

    async def verify_content(self, result: ContentVerification) -> Tuple[bool, str]:
        """Verify content (subject/body) of email."""
        try:
            # Subject checks
            if not result.subject:
                return False, "Empty subject"
            if len(result.subject) > 100:
                return False, "Subject too long"
                
            # Body checks
            if not result.body:
                return False, "Empty body"
            if len(result.body) > 5000:
                return False, "Body too long"
                
            return True, "Content verification passed"
        except Exception as e:
            return False, f"Content verification error: {str(e)}"

    async def verify_general(self, result: Any) -> Tuple[bool, str]:
        """General verification for any result."""
        try:
            if not result:
                return False, "Empty result"
            return True, "General verification passed"
        except Exception as e:
            return False, f"General verification error: {str(e)}"

    async def process_step(self, session: ClientSession, step_data: Dict[str, Any]) -> Tuple[ResultStatus, Any, str]:
        """Process a single step with verification and retries."""
        try:
            function_name = step_data.get("function")
            parameters = step_data.get("parameters", {})
            verification = step_data.get("verification", {})
            reasoning = step_data.get("reasoning", {})
            
            print(f"\nDEBUG: Processing step:")
            print(f"Function: {function_name}")
            print(f"Parameters: {json.dumps(parameters, indent=2)}")
            print(f"Verification: {json.dumps(verification, indent=2)}")
            print(f"Reasoning: {json.dumps(reasoning, indent=2)}")
            
            if not function_name:
                return ResultStatus.FAILURE, None, "Missing function name"
                
            for attempt in range(MAX_RETRIES):
                try:
                    print(f"DEBUG: Attempt {attempt + 1} of {MAX_RETRIES}")
                    result = await session.call_tool(function_name, arguments=parameters)
                    print(f"DEBUG: Tool execution result: {result}")
                    
                    verification_type = VerificationType(verification.get("type", "general"))
                    is_valid, verify_msg = await self.verify_step(result, verification_type)
                    print(f"DEBUG: Verification result: {is_valid}, {verify_msg}")
                    
                    if is_valid:
                        if verification_type == VerificationType.ASCII:
                            values = [int(item.text) for item in result.content]
                            return ResultStatus.SUCCESS, {"values": values}, verify_msg
                        return ResultStatus.SUCCESS, result, verify_msg
                    elif attempt < MAX_RETRIES - 1:
                        print(f"DEBUG: Verification failed, retrying...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        return ResultStatus.FAILURE, None, f"Verification failed after {MAX_RETRIES} attempts: {verify_msg}"
                    
                except Exception as e:
                    print(f"DEBUG: Error in attempt {attempt + 1}: {str(e)}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                        continue
                    return ResultStatus.FAILURE, None, f"Step execution failed: {str(e)}"
                    
        except Exception as e:
            print(f"DEBUG: Unexpected error in process_step: {str(e)}")
            return ResultStatus.FAILURE, None, f"Step processing error: {str(e)}"

    def create_system_prompt(self, tools_description: str, available_tools: str) -> str:
        """Create the enhanced system prompt with strict JSON formatting requirements."""
        return f'''You are an advanced email processing agent with mathematical capabilities.
Follow structured reasoning and strict verification for all operations.

Available Tools:
{tools_description}

AVAILABLE TOOLS (use ONLY these exact names): {available_tools}

Task Processing Guidelines:

1. Planning and Analysis:
   - You can explain your plan and thinking process
   - Break down complex tasks into clear steps
   - Show your reasoning and approach
   - BUT when ready to execute, use exact function call format

2. Response Format Requirements:
   When executing an action, your function call MUST be on its own line in this format:
   FUNCTION_CALL: {{"function": "name", "parameters": {{}}, "verification": {{}}, "reasoning": {{}}}}

   When providing final answer, it MUST be on its own line in this format:
   FINAL_ANSWER: {{"status": "complete", "message": "...", "summary": []}}

3. Example Valid Response:
   Here's my plan:
   1. First, we'll get ASCII values
   2. Then calculate exponentials
   3. Finally send email

   Let's start with step 1:
   FUNCTION_CALL: {{"function": "get_ascii_values", "parameters": {{"string": "INDIA"}}, "verification": {{"type": "ascii_values", "checks": ["range", "charset", "length"]}}, "reasoning": {{"type": "lookup", "explanation": "Get ASCII values", "confidence": 1.0}}}}

4. JSON Structure Requirements:
   Function calls must include:
   - function: Tool name from available tools list
   - parameters: Required parameters for the tool
   - verification: Type and checks for validation
   - reasoning: Type, explanation, and confidence

5. Parameter Types:
   Email Functions:
   - to: "email@example.com"
   - subject: "Subject line"
   - body: "Content"

   ASCII Functions:
   - string: "text"

   Calculation Functions:
   - numbers: [1, 2, 3]
   - value: 123.45

6. Verification Types:
   - email_validation: ["format", "domain", "content"]
   - calculation: ["range", "precision", "overflow"]
   - ascii_values: ["range", "charset", "length"]

7. Reasoning Types:
   - arithmetic: For calculations
   - logic: For decision making
   - lookup: For value retrieval

Remember:
- You can explain your thinking
- Show your plan and steps
- BUT function calls must be in exact format
- Function call must be on its own line
- No markdown in function calls
- Follow JSON structure strictly
'''

    async def run(self, query: str):
        """Main execution loop with enhanced error handling and verification."""
        try:
            server_params = StdioServerParameters(command="python", args=["mcp-server.py"])
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
                    tools = tools_result.tools
                    
                    tools_description = self.format_tools_description(tools)
                    available_tools = ", ".join(tool.name for tool in tools)
                    
                    system_prompt = self.create_system_prompt(tools_description, available_tools)
                    
                    while self.iteration < MAX_ITERATIONS:
                        try:
                            current_prompt = self.prepare_prompt(system_prompt, query)
                            response = await self.get_llm_response(current_prompt)
                            status, result, message = await self.process_llm_response(session, response)
                            
                            if status == ResultStatus.SUCCESS:
                                if message.startswith("FINAL_ANSWER"):
                                    break
                                if hasattr(result, 'function'):
                                    self.history.append({
                                        'function': result.function,
                                        'parameters': result.parameters,
                                        'result': result,
                                        'message': message
                                    })
                            elif status == ResultStatus.FAILURE:
                                print(f"Step failed: {message}")
                                break
                            
                            self.iteration += 1

                        except Exception as e:
                            print(f"Error in iteration {self.iteration}: {str(e)}")
                            break

        except Exception as e:
            print(f"Error in main execution: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources and reset state."""
        self.iteration = 0
        self.history = []
        self.verification_results = []

    def format_tools_description(self, tools) -> str:
        """Format tools description with detailed parameters."""
        try:
            descriptions = []
            for i, tool in enumerate(tools, 1):
                params = tool.inputSchema.get('properties', {})
                param_details = [f"{name}: {info.get('type', 'unknown')}"
                               for name, info in params.items()]
                params_str = ', '.join(param_details)
                desc = getattr(tool, 'description', 'No description available')
                descriptions.append(f"{i}. {tool.name}({params_str}) - {desc}")
            return "\n".join(descriptions)
        except Exception as e:
            print(f"Error formatting tools: {str(e)}")
            return "Error loading tools description"

    async def get_llm_response(self, prompt: str) -> str:
        """Get LLM response with timeout and error handling."""
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.model.generate_content(prompt)
                ),
                timeout=TIMEOUT_SECONDS
            )
            return response.text.strip()
        except TimeoutError:
            raise Exception("LLM response timeout")
        except Exception as e:
            raise Exception(f"LLM response error: {str(e)}")

    def prepare_prompt(self, system_prompt: str, query: str) -> str:
        """Prepare the current prompt with history and next step guidance."""
        history_text = "\n".join(
            f"Step {i+1}: {item.get('function', 'Unknown function')} - {item.get('message', 'No message available')}"
            for i, item in enumerate(self.history)
        )
        
        next_step_guidance = "\nWhat should I do next?" if self.history else ""
        
        return f"""{system_prompt}

History of completed steps:
{history_text}

Current task: {query}
{next_step_guidance}"""

    async def process_llm_response(self, session: ClientSession, response: str) -> Tuple[ResultStatus, Any, str]:
        """Process LLM response with enhanced JSON validation and planning text handling."""
        try:
            response_text = response.strip()
            
            print("\n=== LLM Full Response ===")
            print(response_text)
            print("========================\n")
            
            function_call_match = None
            final_answer_match = None
            
            for line in response_text.split('\n'):
                line = line.strip()
                if "FUNCTION_CALL:" in line:
                    function_call_match = line
                    break
                elif "FINAL_ANSWER:" in line:
                    final_answer_match = line
                    break

            if function_call_match:
                try:
                    json_str = function_call_match.split("FUNCTION_CALL:", 1)[1].strip()
                    print(f"DEBUG: Extracted JSON string: {json_str}")
                    
                    data = json.loads(json_str)
                    print(f"DEBUG: Parsed JSON data: {json.dumps(data, indent=2)}")
                    
                    if data.get('function') == 'send_email':
                        for history_item in self.history:
                            if (history_item.get('function') == 'send_email' and 
                                history_item.get('parameters', {}).get('to_email') == data['parameters'].get('to_email')):
                                print("DEBUG: Email already sent in this session, skipping")
                                return ResultStatus.SUCCESS, None, "Email already sent"
                    
                    if data.get('function') == 'send_email' and 'parameters' in data:
                        params = data['parameters']
                        print(f"DEBUG: Original email parameters: {json.dumps(params, indent=2)}")
                        
                        if params.get('image_path') is None:
                            params['image_path'] = ''
                            print("DEBUG: Set empty image_path")
                        
                        required_params = ['to_email', 'subject', 'body']
                        for param in required_params:
                            if param not in params:
                                print(f"DEBUG: Missing required parameter: {param}")
                                return ResultStatus.FAILURE, None, f"Missing required parameter: {param}"
                        
                        print(f"DEBUG: Final email parameters: {json.dumps(params, indent=2)}")
                        
                        if 'verification' in data:
                            if isinstance(data['verification'], dict) and 'email_validation' in data['verification']:
                                data['verification'] = {
                                    'type': 'email_validation',
                                    'checks': data['verification']['email_validation']
                                }
                                print(f"DEBUG: Updated verification structure: {json.dumps(data['verification'], indent=2)}")
                    
                    if self.history:
                        last_step = self.history[-1]
                        if (last_step.get('function') == data['function'] and 
                            last_step.get('parameters') == data['parameters']):
                            print("DEBUG: Skipping already completed step")
                            return ResultStatus.SUCCESS, last_step['result'], "Step already completed"
                    
                    try:
                        function_call = FunctionCall(**data)
                        result = await self.process_step(session, data)
                        print(f"DEBUG: Process step result: {result}")
                        
                        if result[0] == ResultStatus.SUCCESS:
                            self.history.append({
                                'function': data['function'],
                                'parameters': data['parameters'],
                                'result': result[1],
                                'message': result[2]
                            })
                        
                        return result
                    except Exception as e:
                        print(f"DEBUG: Function call validation error: {str(e)}")
                        return ResultStatus.FAILURE, None, f"Invalid function call format: {str(e)}"
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Invalid JSON format: {str(e)}"
                except Exception as e:
                    print(f"DEBUG: Function call processing error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Error processing function call: {str(e)}"
                
            elif final_answer_match:
                try:
                    json_str = final_answer_match.split("FINAL_ANSWER:", 1)[1].strip()
                    print(f"DEBUG: Extracted final answer JSON: {json_str}")
                    
                    data = json.loads(json_str)
                    print(f"DEBUG: Parsed final answer data: {json.dumps(data, indent=2)}")
                    
                    try:
                        final_answer = FinalAnswer(**data)
                        return ResultStatus.SUCCESS, data, "Final answer received"
                    except Exception as e:
                        print(f"DEBUG: Final answer validation error: {str(e)}")
                        return ResultStatus.FAILURE, None, f"Invalid final answer format: {str(e)}"
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: Final answer JSON decode error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Invalid final answer format: {str(e)}"
                except Exception as e:
                    print(f"DEBUG: Final answer processing error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Error processing final answer: {str(e)}"
            else:
                print(f"DEBUG: No valid function call or final answer found in response")
                print("DEBUG: Response must contain a line starting with FUNCTION_CALL: or FINAL_ANSWER:")
                return ResultStatus.FAILURE, None, "Response must contain FUNCTION_CALL: or FINAL_ANSWER:"

        except Exception as e:
            print(f"DEBUG: Unexpected error in process_llm_response: {str(e)}")
            return ResultStatus.FAILURE, None, f"Unexpected error: {str(e)}"

if __name__ == "__main__":
    agent = EmailAgent()
    query = """Find the ASCII values of characters in the word "INDIA", then calculate the sum of exponentials of those ASCII values.
               Mail the final answer to me. My email address is "sunilks.eminem@gmail.com"
            """
    asyncio.run(agent.run(query))
