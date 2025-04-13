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
from typing import Dict, List, Any, Tuple, Optional
from enum import Enum
from jsonschema import validate, ValidationError, FormatChecker
import logging
from mcp.types import CallToolResult, TextContent

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
    PENDING = "pending"

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

class VerificationHandler:
    """Handles verification of different types of results"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def verify_step(self, step_result: Dict[str, Any], verification_type: VerificationType) -> Tuple[bool, str]:
        """
        Verify a step result based on its type.
        
        Args:
            step_result: The result to verify
            verification_type: The type of verification to perform
            
        Returns:
            Tuple of (success, message) where success is a boolean and message is a string
        """
        try:
            self.logger.debug(f"Verifying step with type: {verification_type}")
            self.logger.debug(f"Step result type: {type(step_result)}")
            self.logger.debug(f"Step result: {step_result}")

            if verification_type == VerificationType.ASCII:
                return await self._verify_ascii(step_result)
            elif verification_type == VerificationType.CALCULATION:
                return await self._verify_calculation(step_result)
            elif verification_type == VerificationType.EMAIL:
                return await self._verify_email(step_result)
            elif verification_type == VerificationType.CONTENT:
                return await self._verify_content(step_result)
            else:
                return await self._verify_general(step_result)

        except Exception as e:
            self.logger.error(f"Verification error: {str(e)}")
            return False, f"Verification failed: {str(e)}"

    async def _verify_ascii(self, step_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify ASCII values result"""
        try:
            if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                values = [int(item.text) for item in step_result.content]
                self.logger.debug(f"Extracted ASCII values: {values}")
                
                # Validate ASCII values
                if not all(0 <= v <= 127 for v in values):
                    return False, "Invalid ASCII value range"
                
                return True, f"Valid ASCII values: {values}"
            return False, "Invalid ASCII result format"
        except Exception as e:
            self.logger.error(f"ASCII verification error: {str(e)}")
            return False, f"ASCII verification failed: {str(e)}"

    async def _verify_calculation(self, step_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify calculation result"""
        try:
            self.logger.debug("Starting calculation verification")
            
            if not hasattr(step_result, 'content'):
                return False, "Invalid calculation result format"
            
            content_text = step_result.content[0].text
            self.logger.debug(f"Content text: {content_text}")
            
            outer_data = json.loads(content_text)
            self.logger.debug(f"Outer data: {outer_data}")
            
            inner_data = json.loads(outer_data['content'][0]['text'])
            self.logger.debug(f"Inner data: {inner_data}")
            
            result = inner_data['data']['result']
            self.logger.debug(f"Extracted result value: {result}")
            
            if not isinstance(result, (int, float)):
                return False, "Invalid calculation result type"
            
            return True, f"Valid calculation result: {result}"
            
        except Exception as e:
            self.logger.error(f"Calculation verification error: {str(e)}")
            return False, f"Calculation verification failed: {str(e)}"

    async def _verify_email(self, step_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify email result"""
        try:
            if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                content_text = step_result.content[0].text
                self.logger.debug(f"Email content text: {content_text}")
                
                outer_data = json.loads(content_text)
                self.logger.debug(f"Email outer data: {outer_data}")
                
                inner_data = json.loads(outer_data['content'][0]['text'])
                self.logger.debug(f"Email inner data: {inner_data}")
                
                if inner_data.get('is_valid', False):
                    return True, "Email verification passed"
            return False, "Invalid email result format"
        except Exception as e:
            self.logger.error(f"Email verification error: {str(e)}")
            return False, f"Email verification failed: {str(e)}"

    async def _verify_content(self, step_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify content result"""
        try:
            if hasattr(step_result, 'parameters'):
                subject = step_result.parameters.get('subject', '')
                body = step_result.parameters.get('body', '')
                self.logger.debug(f"Extracted content - subject: {subject}, body length: {len(body)}")
                
                if not subject or not body:
                    return False, "Missing subject or body"
                
                return True, "Content verification passed"
            return False, "Invalid content result format"
        except Exception as e:
            self.logger.error(f"Content verification error: {str(e)}")
            return False, f"Content verification failed: {str(e)}"

    async def _verify_general(self, step_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify general result"""
        try:
            self.logger.debug(f"Using general verification for result: {step_result}")
            return True, "General verification passed"
        except Exception as e:
            self.logger.error(f"General verification error: {str(e)}")
            return False, f"General verification failed: {str(e)}"

class EmailProcessor:
    """Handles email-related operations and verifications"""
    
    def __init__(self):
        self.required_email_params = ['to_email', 'subject', 'body']
        self.required_ascii_params = ['string']
        self.required_calculation_params = ['numbers']
        self.required_content_params = ['subject', 'body']
        self.logger = logging.getLogger(__name__)
        self._last_email_time = 0
        self._email_rate_limit = 60  # seconds between emails

    def validate_email_parameters(self, params: Dict[str, Any]) -> None:
        """
        Validate email parameters with detailed checks.
        
        Args:
            params: Dictionary of email parameters
            
        Raises:
            ParameterError: If parameters are invalid
        """
        try:
            # Check required parameters
            missing_params = [p for p in self.required_email_params if p not in params]
            if missing_params:
                raise ParameterError(f"Missing required email parameters: {missing_params}")
            
            # Validate email format
            email = params['to_email']
            if not isinstance(email, str):
                raise ParameterError("Email address must be a string")
            if '@' not in email or '.' not in email.split('@')[1]:
                raise ParameterError("Invalid email address format")
            
            # Validate subject
            subject = params.get('subject', '')
            if not isinstance(subject, str):
                raise ParameterError("Subject must be a string")
            if len(subject.strip()) == 0:
                raise ParameterError("Subject cannot be empty")
            
            # Validate body
            body = params.get('body', '')
            if not isinstance(body, str):
                raise ParameterError("Body must be a string")
            if len(body.strip()) == 0:
                raise ParameterError("Body cannot be empty")
            
            # Validate image_path if present
            image_path = params.get('image_path')
            if image_path is not None and not isinstance(image_path, str):
                raise ParameterError("Image path must be a string or None")
                
        except Exception as e:
            self.logger.error(f"Email parameter validation error: {str(e)}")
            raise

    def check_rate_limit(self) -> bool:
        """
        Check if email can be sent based on rate limit.
        
        Returns:
            bool: True if email can be sent, False if rate limited
        """
        current_time = time.time()
        if current_time - self._last_email_time < self._email_rate_limit:
            self.logger.warning("Email rate limit exceeded")
            return False
        self._last_email_time = current_time
        return True

    def prepare_email_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare and sanitize email parameters.
        
        Args:
            params: Raw email parameters
            
        Returns:
            Dict[str, Any]: Sanitized email parameters
        """
        try:
            # Create a copy of parameters
            prepared_params = params.copy()
            
            # Ensure required parameters exist
            for param in self.required_email_params:
                if param not in prepared_params:
                    prepared_params[param] = ''
            
            # Sanitize email address
            prepared_params['to_email'] = prepared_params['to_email'].strip().lower()
            
            # Sanitize subject and body
            prepared_params['subject'] = prepared_params['subject'].strip()
            prepared_params['body'] = prepared_params['body'].strip()
            
            # Handle image_path
            if prepared_params.get('image_path') is None:
                prepared_params['image_path'] = ''
            
            self.logger.debug(f"Prepared email parameters: {prepared_params}")
            return prepared_params
            
        except Exception as e:
            self.logger.error(f"Error preparing email parameters: {str(e)}")
            raise

    def validate_ascii_parameters(self, params: Dict[str, Any]) -> None:
        """
        Validate ASCII parameters with detailed checks.
        
        Args:
            params: Dictionary of ASCII parameters
            
        Raises:
            ParameterError: If parameters are invalid
        """
        try:
            if 'string' not in params:
                raise ParameterError("Missing required parameter: string")
            if not isinstance(params['string'], str):
                raise ParameterError("String parameter must be a string")
            if len(params['string'].strip()) == 0:
                raise ParameterError("String cannot be empty")
                
        except Exception as e:
            self.logger.error(f"ASCII parameter validation error: {str(e)}")
            raise

    def validate_calculation_parameters(self, params: Dict[str, Any]) -> None:
        """
        Validate calculation parameters with detailed checks.
        
        Args:
            params: Dictionary of calculation parameters
            
        Raises:
            ParameterError: If parameters are invalid
        """
        try:
            if 'numbers' not in params:
                raise ParameterError("Missing required parameter: numbers")
            if not isinstance(params['numbers'], list):
                raise ParameterError("Numbers parameter must be a list")
            if not all(isinstance(n, (int, float)) for n in params['numbers']):
                raise ParameterError("All numbers must be integers or floats")
                
        except Exception as e:
            self.logger.error(f"Calculation parameter validation error: {str(e)}")
            raise

    def validate_content_parameters(self, params: Dict[str, Any]) -> None:
        """
        Validate content parameters with detailed checks.
        
        Args:
            params: Dictionary of content parameters
            
        Raises:
            ParameterError: If parameters are invalid
        """
        try:
            missing_params = [p for p in self.required_content_params if p not in params]
            if missing_params:
                raise ParameterError(f"Missing required content parameters: {missing_params}")
            
            if not isinstance(params.get('subject', ''), str):
                raise ParameterError("Subject must be a string")
            if not isinstance(params.get('body', ''), str):
                raise ParameterError("Body must be a string")
                
        except Exception as e:
            self.logger.error(f"Content parameter validation error: {str(e)}")
            raise

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
            print(f"DEBUG: Verifying step with type: {verification_type}")
            print(f"DEBUG: Step result type: {type(step_result)}")
            print(f"DEBUG: Step result: {step_result}")

            # Extract result content based on verification type
            if verification_type == VerificationType.ASCII:
                # For ASCII values, we need to convert TextContent to integers
                if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                    values = [int(item.text) for item in step_result.content]
                    print(f"DEBUG: Extracted ASCII values: {values}")
                    return await self.verify_ascii({"values": values})
            elif verification_type == VerificationType.CALCULATION:
                # For calculations, pass the raw result to verify_calculation
                print(f"DEBUG: Passing raw result to verify_calculation: {step_result}")
                return await self.verify_calculation(step_result)
            elif verification_type == VerificationType.EMAIL:
                # For email, check if the result indicates success
                if hasattr(step_result, 'content') and isinstance(step_result.content, list):
                    try:
                        # Get the first content item's text
                        content_text = step_result.content[0].text
                        print(f"DEBUG: Email content text: {content_text}")
                        
                        # Parse the outer JSON string
                        outer_data = json.loads(content_text)
                        print(f"DEBUG: Email outer data: {outer_data}")
                        
                        # Parse the inner JSON string from the content array
                        inner_data = json.loads(outer_data['content'][0]['text'])
                        print(f"DEBUG: Email inner data: {inner_data}")
                        
                        if inner_data.get('is_valid', False):
                            return True, "Email verification passed"
                    except (json.JSONDecodeError, IndexError, AttributeError) as e:
                        print(f"DEBUG: Email verification error: {str(e)}")
                        return False, f"Email verification error: {str(e)}"
                return False, "Invalid email result format"
            elif verification_type == VerificationType.CONTENT:
                # For content, extract subject and body
                if hasattr(step_result, 'parameters'):
                    subject = step_result.parameters.get('subject', '')
                    body = step_result.parameters.get('body', '')
                    print(f"DEBUG: Extracted content - subject: {subject}, body length: {len(body)}")
                    return await self.verify_content({"subject": subject, "body": body})
            else:
                # For general verification, pass the raw result
                print(f"DEBUG: Using general verification for result: {step_result}")
                return await self.verify_general(step_result)

            return False, "Unsupported verification type or invalid result format"
        except Exception as e:
            print(f"DEBUG: Verification error: {str(e)}")
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
            print(f"DEBUG: Starting calculation verification")
            print(f"DEBUG: Result type: {type(result)}")
            print(f"DEBUG: Raw result: {result}")

            # Handle case where result is a string
            if isinstance(result, str):
                try:
                    print(f"DEBUG: Parsing string result as JSON")
                    result = json.loads(result)
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {str(e)}")
                    return False, "Invalid JSON string format"

            # Extract the result from the complex response structure
            if hasattr(result, 'content') and isinstance(result.content, list):
                print(f"DEBUG: Processing content list")
                # Get the first content item's text
                content_text = result.content[0].text
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

    async def verify_ascii(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """Verify ASCII values."""
        try:
            values = result.get("values", [])
            if not values:
                return False, "No ASCII values found"

            # Convert all values to integers
            try:
                values = [int(v) for v in values]
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
                        # For ASCII values, extract the actual values from the result
                        if verification_type == VerificationType.ASCII:
                            values = [int(item.text) for item in result.content]
                            return ResultStatus.SUCCESS, {"values": values}, verify_msg
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
            # Initialize MCP connection
            server_params = StdioServerParameters(command="python", args=["mcp-server-enhanced.py"])
            
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
                                if message.startswith("FINAL_ANSWER"):
                                    break
                                # Add the result to history
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
        # Format history with step numbers and results
        history_text = "\n".join(
            f"Step {i+1}: {item.get('function', 'Unknown function')} - {item.get('message', 'No message available')}"
            for i, item in enumerate(self.history)
        )
        
        # Add next step guidance
        next_step_guidance = "\nWhat should I do next?" if self.history else ""
        
        # Combine all parts
        return f"""{system_prompt}

History of completed steps:
{history_text}

Current task: {query}
{next_step_guidance}"""

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
                    required_params = ["to_email", "subject", "body"]
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
        """Process LLM response with enhanced JSON validation and planning text handling."""
        try:
            # Clean up response text
            response_text = response.strip()
            
            # Print the full response for visibility
            print("\n=== LLM Full Response ===")
            print(response_text)
            print("========================\n")
            
            # Look for function call or final answer in the response
            function_call_match = None
            final_answer_match = None
            
            # Check each line for function call or final answer
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
                    # Extract JSON part
                    json_str = function_call_match.split("FUNCTION_CALL:", 1)[1].strip()
                    print(f"DEBUG: Extracted JSON string: {json_str}")
                    
                    # Parse JSON
                    data = json.loads(json_str)
                    print(f"DEBUG: Parsed JSON data: {json.dumps(data, indent=2)}")
                    
                    # Fix email parameters if needed
                    if data.get('function') == 'send_email' and 'parameters' in data:
                        params = data['parameters']
                        print(f"DEBUG: Original email parameters: {json.dumps(params, indent=2)}")
                        
                        # Handle image_path
                        if params.get('image_path') is None:
                            params['image_path'] = ''
                            print("DEBUG: Set empty image_path")
                        
                        # Ensure all required parameters are present
                        required_params = ['to_email', 'subject', 'body']
                        for param in required_params:
                            if param not in params:
                                print(f"DEBUG: Missing required parameter: {param}")
                                return ResultStatus.FAILURE, None, f"Missing required parameter: {param}"
                        
                        print(f"DEBUG: Final email parameters: {json.dumps(params, indent=2)}")
                        
                        # Fix verification structure
                        if 'verification' in data:
                            if isinstance(data['verification'], dict) and 'email_validation' in data['verification']:
                                data['verification'] = {
                                    'type': 'email_validation',
                                    'checks': data['verification']['email_validation']
                                }
                                print(f"DEBUG: Updated verification structure: {json.dumps(data['verification'], indent=2)}")
                    
                    # Check if this step has already been completed
                    if self.history:
                        last_step = self.history[-1]
                        if (last_step.get('function') == data['function'] and 
                            last_step.get('parameters') == data['parameters']):
                            print("DEBUG: Skipping already completed step")
                            return ResultStatus.SUCCESS, last_step['result'], "Step already completed"
                    
                    # Validate JSON structure
                    is_valid, msg = await self.validate_json_structure(data, "function_call")
                    if not is_valid:
                        print(f"DEBUG: JSON validation failed: {msg}")
                        return ResultStatus.FAILURE, None, f"Invalid JSON format: {msg}"
                    
                    # Process the validated function call
                    result = await self.process_step(session, data)
                    print(f"DEBUG: Process step result: {result}")
                    
                    # Store the step in history
                    if result[0] == ResultStatus.SUCCESS:
                        self.history.append({
                            'function': data['function'],
                            'parameters': data['parameters'],
                            'result': result[1],
                            'message': result[2]  # Store the message from the result
                        })
                    
                    return result
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Invalid JSON format: {str(e)}"
                except Exception as e:
                    print(f"DEBUG: Function call processing error: {str(e)}")
                    return ResultStatus.FAILURE, None, f"Error processing function call: {str(e)}"
                
            elif final_answer_match:
                try:
                    # Extract JSON part
                    json_str = final_answer_match.split("FINAL_ANSWER:", 1)[1].strip()
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
