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
from enum import Enum
from jsonschema import validate, ValidationError, FormatChecker

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Constants
MAX_ITERATIONS = 6
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10

# Verification Types
class VerificationType(Enum):
    EMAIL = "email_validation"
    CALCULATION = "calculation"
    ASCII = "ascii_values"
    CONTENT = "content_validation"
    GENERAL = "general"

# Result Status
class ResultStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"

class JsonSchema:
    """JSON schema definitions for request/response validation"""
    
    FUNCTION_CALL = {
        "type": "object",
        "required": ["function", "parameters", "verification"],
        "properties": {
            "function": {"type": "string"},
            "parameters": {"type": "object"},
            "verification": {
                "type": "object",
                "required": ["type", "checks"],
                "properties": {
                    "type": {"type": "string"},
                    "checks": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
    
    FINAL_ANSWER = {
        "type": "object",
        "required": ["status", "message", "summary"],
        "properties": {
            "status": {"type": "string"},
            "message": {"type": "string"},
            "summary": {"type": "array", "items": {"type": "string"}}
        }
    }

class JsonSchemaValidator:
    """JSON Schema validator with custom validation rules"""
    
    def __init__(self):
        self.format_checker = FormatChecker()
        
    def validate(self, instance: Dict, schema: Dict) -> Tuple[bool, str]:
        """Validate JSON instance against schema.
        
        Args:
            instance: JSON data to validate
            schema: JSON schema to validate against
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            validate(instance=instance, schema=schema, format_checker=self.format_checker)
            return True, "Validation successful"
        except ValidationError as e:
            return False, f"Validation error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error during validation: {str(e)}"
            
    def validate_function_call(self, data: Dict) -> Tuple[bool, str]:
        """Validate function call JSON structure."""
        schema = {
            "type": "object",
            "required": ["function", "parameters", "verification"],
            "properties": {
                "function": {"type": "string"},
                "parameters": {"type": "object"},
                "verification": {
                    "type": "object",
                    "required": ["type", "checks"],
                    "properties": {
                        "type": {"type": "string"},
                        "checks": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "reasoning": {
                    "type": "object",
                    "required": ["type", "explanation", "confidence"],
                    "properties": {
                        "type": {"type": "string"},
                        "explanation": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        }
                    }
                }
            }
        }
        return self.validate(data, schema)
        
    def validate_final_answer(self, data: Dict) -> Tuple[bool, str]:
        """Validate final answer JSON structure."""
        schema = {
            "type": "object",
            "required": ["status", "message", "summary", "confidence"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["complete", "partial", "failed"]
                },
                "message": {"type": "string"},
                "summary": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "fallback_suggestions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
        return self.validate(data, schema)

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
        
        # Add JSON schema validator
        self.json_validator = JsonSchemaValidator()

    async def verify_step(self, step_result: Dict[str, Any], verification_type: VerificationType) -> Tuple[bool, str]:
        """Verify a single step result with detailed checking."""
        try:
            verification_funcs = {
                VerificationType.EMAIL: self.verify_email,
                VerificationType.CALCULATION: self.verify_calculation,
                VerificationType.ASCII: self.verify_ascii,
                VerificationType.CONTENT: self.verify_content,
                VerificationType.GENERAL: self.verify_general
            }
            
            verify_func = verification_funcs.get(verification_type, self.verify_general)
            return await verify_func(step_result)
        except Exception as e:
            return False, f"Verification failed: {str(e)}"

    async def verify_email(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify email-related operations."""
        try:
            email = result.get("email", "")
            if not isinstance(email, str):
                return False, "Invalid email type"
            
            # Basic format check
            if not "@" in email or not "." in email:
                return False, "Invalid email format"
                
            # Length check
            if len(email) > 254:  # RFC 5321
                return False, "Email too long"
                
            return True, "Email verification passed"
        except Exception as e:
            return False, f"Email verification error: {str(e)}"

    async def verify_calculation(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify calculation results."""
        try:
            value = result.get("value")
            if not isinstance(value, (int, float)):
                return False, "Invalid numerical type"
                
            # Range check
            if abs(value) > 1e308:  # Max float value
                return False, "Result too large"
                
            # NaN/Inf check
            if isinstance(value, float) and (value != value or value == float('inf')):
                return False, "Invalid numerical result"
                
            return True, "Calculation verification passed"
        except Exception as e:
            return False, f"Calculation verification error: {str(e)}"

    async def verify_ascii(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify ASCII values."""
        try:
            values = result.get("values", [])
            if not isinstance(values, list):
                return False, "Expected list of ASCII values"
                
            # Valid ASCII range check
            if not all(isinstance(x, int) and 0 <= x <= 127 for x in values):
                return False, "Invalid ASCII values found"
                
            return True, "ASCII verification passed"
        except Exception as e:
            return False, f"ASCII verification error: {str(e)}"

    async def verify_content(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify content (subject/body) of email."""
        try:
            subject = result.get("subject", "")
            body = result.get("body", "")
            
            # Subject checks
            if not subject:
                return False, "Empty subject"
            if len(subject) > 100:
                return False, "Subject too long"
                
            # Body checks
            if not body:
                return False, "Empty body"
            if len(body) > 5000:
                return False, "Body too long"
                
            return True, "Content verification passed"
        except Exception as e:
            return False, f"Content verification error: {str(e)}"

    async def verify_general(self, result: Dict[str, Any]) -> Tuple[bool, str]:
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
            # Extract step information
            function_name = step_data.get("function")
            parameters = step_data.get("parameters", {})
            verification = step_data.get("verification", {})
            reasoning = step_data.get("reasoning", {})
            
            # Debug logging
            print(f"\nDEBUG: Processing step:")
            print(f"Function: {function_name}")
            print(f"Parameters: {json.dumps(parameters, indent=2)}")
            print(f"Verification: {json.dumps(verification, indent=2)}")
            print(f"Reasoning: {json.dumps(reasoning, indent=2)}")
            
            # Validate step data
            if not function_name:
                return ResultStatus.FAILURE, None, "Missing function name"
                
            # Execute with retries
            for attempt in range(MAX_RETRIES):
                try:
                    print(f"DEBUG: Attempt {attempt + 1} of {MAX_RETRIES}")
                    
                    # Execute tool
                    result = await session.call_tool(function_name, arguments=parameters)
                    print(f"DEBUG: Tool execution result: {result}")
                    
                    # Verify result
                    verification_type = VerificationType(verification.get("type", "general"))
                    is_valid, verify_msg = await self.verify_step(result, verification_type)
                    print(f"DEBUG: Verification result: {is_valid}, {verify_msg}")
                    
                    if is_valid:
                        return ResultStatus.SUCCESS, result, verify_msg
                    elif attempt < MAX_RETRIES - 1:
                        print(f"DEBUG: Verification failed, retrying...")
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    else:
                        return ResultStatus.FAILURE, None, f"Verification failed after {MAX_RETRIES} attempts: {verify_msg}"
                        
                except Exception as e:
                    print(f"DEBUG: Error in attempt {attempt + 1}: {str(e)}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)  # Wait before retry
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

1. Analysis & Planning:
   - Break down complex tasks into clear steps
   - Validate inputs before processing
   - Plan verification steps for each operation
   - Consider potential failure points
   - EXPLICITLY state your reasoning type (arithmetic/logic/lookup)

2. Execution Format (STRICT JSON):
   For function calls, you MUST use this exact format:
   ```json
   {{
     "function": "function_name",
     "parameters": {{
       "to": "email@example.com",       # for email functions
       "subject": "Subject line",       # for email functions
       "body": "Email content",         # for email functions
       "string": "text",               # for ASCII functions
       "numbers": [1, 2, 3],           # for calculation functions
       "value": 123.45                 # for verification functions
     }},
     "verification": {{
       "type": "verification_type",    # Must be one of: email_validation, calculation, ascii_values
       "checks": [                     # Must match the verification type:
         "format",                     # For email: format, domain, content
         "domain",                     # For calculation: range, precision, overflow
         "content"                     # For ASCII: range, charset, length
       ]
     }},
     "reasoning": {{
       "type": "arithmetic|logic|lookup",
       "explanation": "Brief explanation of the reasoning used",
       "confidence": 0.95              # Confidence score between 0 and 1
     }}
   }}
   ```

3. Conversation Context Management:
   - Each response must reference previous steps if any
   - Include step number and relation to previous steps
   - Update your understanding based on previous results
   - Example: "Based on step 2's ASCII values [65,66], now calculating..."

4. Self-Verification Steps:
   Before executing any operation:
   1. Validate inputs match expected format
   2. Check if operation makes sense in current context
   3. Verify prerequisites are met
   4. Estimate expected output range
   5. Compare actual output with expectations

5. Error Handling and Fallbacks:
   If primary approach fails:
   1. Log the error and reason
   2. Try alternative approach if available
   3. If uncertain (confidence < 0.8):
      - State your uncertainty
      - List alternative approaches
      - Request clarification if needed
   4. If tool fails:
      - Report specific error
      - Suggest workaround
      - Consider manual calculation

6. Response Formats:
   A. For function calls:
   FUNCTION_CALL: {{
     "function": "name",
     "parameters": {...},
     "verification": {...},
     "reasoning": {{
       "type": "arithmetic|logic|lookup",
       "explanation": "...",
       "confidence": 0.95
     }}
   }}

   B. For final answers:
   FINAL_ANSWER: {{
     "status": "complete|partial|failed",
     "message": "...",
     "summary": [...],
     "confidence": 0.95,
     "fallback_suggestions": [...]
   }}

7. Progress Tracking:
   - Maintain numbered steps
   - Reference previous results
   - Track completion status
   - Report confidence levels
   - Log verification results

Remember:
- Use exact function names from tools list
- Follow JSON structure strictly
- Include all required fields
- Use correct verification types and checks
- Always perform self-checks
- Maintain conversation context
- Have fallback plans ready
'''

    async def run(self, query: str):
        """Main execution loop with enhanced error handling and verification."""
        try:
            # Initialize MCP connection
            server_params = StdioServerParameters(command="python", args=["mcp-server.py"])
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Get tools
                    tools_result = await session.list_tools()
                    tools = tools_result.tools
                    
                    # Create tools description
                    tools_description = self.format_tools_description(tools)
                    available_tools = ", ".join(tool.name for tool in tools)
                    
                    # Create system prompt
                    system_prompt = self.create_system_prompt(tools_description, available_tools)
                    
                    # Main processing loop
                    while self.iteration < MAX_ITERATIONS:
                        try:
                            # Prepare current prompt
                            current_prompt = self.prepare_prompt(system_prompt, query)
                            
                            # Get LLM response
                            response = await self.get_llm_response(current_prompt)
                            
                            # Process response
                            status, result, message = await self.process_llm_response(session, response)
                            
                            # Handle result
                            if status == ResultStatus.SUCCESS:
                                self.history.append({"step": self.iteration + 1, "result": result, "message": message})
                                if message.startswith("FINAL_ANSWER"):
                                    break
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
        """Prepare the current prompt with history."""
        history_text = "\n".join(
            f"Step {item['step']}: {item['message']}"
            for item in self.history
        )
        return f"{system_prompt}\n\nHistory:\n{history_text}\n\nQuery: {query}"

    async def validate_json_structure(self, data: Dict, schema_type: str) -> Tuple[bool, str]:
        """Validate JSON structure against defined schemas."""
        try:
            if schema_type == "function_call":
                schema = JsonSchema.FUNCTION_CALL
            elif schema_type == "final_answer":
                schema = JsonSchema.FINAL_ANSWER
            else:
                return False, f"Unknown schema type: {schema_type}"
            
            # Validate structure
            self.json_validator.validate(data, schema)
            
            # Additional validation based on function type
            if schema_type == "function_call":
                func_name = data["function"]
                if func_name == "send_email":
                    required_params = ["to", "subject", "body"]
                    for param in required_params:
                        if param not in data["parameters"]:
                            return False, f"Missing required parameter: {param}"
                
                # Verify check types based on verification type
                valid_checks = {
                    "email_validation": ["format", "domain", "content"],
                    "calculation": ["range", "precision", "overflow"],
                    "ascii_values": ["range", "charset", "length"],
                }
                
                v_type = data["verification"]["type"]
                if v_type in valid_checks:
                    invalid_checks = [c for c in data["verification"]["checks"] 
                                   if c not in valid_checks[v_type]]
                    if invalid_checks:
                        return False, f"Invalid checks for {v_type}: {invalid_checks}"
            
            return True, "JSON structure valid"
            
        except Exception as e:
            return False, f"JSON validation error: {str(e)}"

    async def process_llm_response(self, session: ClientSession, response: str) -> Tuple[ResultStatus, Any, str]:
        """Process LLM response with enhanced JSON validation."""
        try:
            # Clean up response text
            response_text = response.strip()
            
            # Debug logging
            print(f"\nDEBUG: Raw LLM response: {response_text}")
            
            if "FUNCTION_CALL:" in response_text:
                try:
                    # Extract JSON part
                    json_str = response_text.split("FUNCTION_CALL:", 1)[1].strip()
                    print(f"DEBUG: Extracted JSON string: {json_str}")
                    
                    # Parse JSON
                    data = json.loads(json_str)
                    print(f"DEBUG: Parsed JSON data: {json.dumps(data, indent=2)}")
                    
                    # Validate JSON structure
                    is_valid, msg = await self.validate_json_structure(data, "function_call")
                    if not is_valid:
                        print(f"DEBUG: JSON validation failed: {msg}")
                        return ResultStatus.FAILURE, None, f"Invalid JSON format: {msg}"
                    
                    # Process the validated function call
                    result = await self.process_step(session, data)
                    print(f"DEBUG: Process step result: {result}")
                    return result
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Invalid JSON format: {str(e)}"
                except Exception as e:
                    print(f"DEBUG: Function call processing error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Error processing function call: {str(e)}"
                
            elif "FINAL_ANSWER:" in response_text:
                try:
                    # Extract JSON part
                    json_str = response_text.split("FINAL_ANSWER:", 1)[1].strip()
                    print(f"DEBUG: Extracted final answer JSON: {json_str}")
                    
                    # Parse JSON
                    data = json.loads(json_str)
                    print(f"DEBUG: Parsed final answer data: {json.dumps(data, indent=2)}")
                    
                    # Validate JSON structure
                    is_valid, msg = await self.validate_json_structure(data, "final_answer")
                    if not is_valid:
                        print(f"DEBUG: Final answer validation failed: {msg}")
                        return ResultStatus.FAILURE, None, f"Invalid final answer format: {msg}"
                    
                    return ResultStatus.SUCCESS, data, "Final answer received"
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: Final answer JSON decode error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Invalid final answer format: {str(e)}"
                except Exception as e:
                    print(f"DEBUG: Final answer processing error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Error processing final answer: {str(e)}"
            else:
                print(f"DEBUG: Invalid response format - no recognized prefix")
                return ResultStatus.FAILURE, None, "Response must start with FUNCTION_CALL: or FINAL_ANSWER:"
                
        except Exception as e:
            print(f"DEBUG: Unexpected error in process_llm_response: {str(e)}")
            return ResultStatus.FAILURE, None, f"Unexpected error: {str(e)}"

if __name__ == "__main__":
    agent = EmailAgent()
    query = """Find the ASCII values of characters in the word "INDIA", then calculate the sum of exponentials of those ASCII values.
               Mail the final answer to me. My email address is "sunilks.eminem@gmail.com"
            """
    asyncio.run(agent.run(query))
