from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import pyautogui
import subprocess
import time
import asyncio
import os
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import json
import smtplib
from typing import Any, Tuple, List, Dict, Optional
from pydantic import BaseModel, Field, ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import re
import numpy as np
from decimal import Decimal, getcontext
from dotenv import load_dotenv

console = Console()
mcp = FastMCP("EmailAgent")

# Load environment variables
load_dotenv()

# Set high precision for decimal calculations
getcontext().prec = 50

# Pydantic Models
class ReasoningStep(BaseModel):
    description: str
    type: str
    confidence: float = Field(ge=0.0, le=1.0)

class ShowReasoningInput(BaseModel):
    steps: List[ReasoningStep]

class TextResponse(BaseModel):
    content: TextContent

class VerifyInput(BaseModel):
    expression: str
    expected: float

class CheckConsistencyInput(BaseModel):
    steps: List[str]

class ConsistencyResult(BaseModel):
    consistency_score: float
    issues: List[str]
    warnings: List[str]
    insights: List[str]

class GetAsciiInput(BaseModel):
    string: str = Field(...)
    input_data: Optional[str] = None  # Make this optional for backward compatibility 

class CalculateExponentialInput(BaseModel):
    numbers: List[int]

class SendEmailInput(BaseModel):
    to_email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    subject: str
    body: str
    image_path: Optional[str] = None

# Add Gmail OAuth2 configuration at the top of the file
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_FILE = 'token.json'
CLIENT_SECRETS_FILE = 'client_secrets.json'

def get_gmail_service():
    """Get Gmail service using OAuth2 credentials."""
    creds = None
    
    # Load token from file if it exists
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as token:
                creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
        except Exception as e:
            console.print(f"[yellow]Warning: Error loading token file: {str(e)}[/yellow]")
            console.print("[yellow]Will attempt to create new credentials...[/yellow]")
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                console.print(f"[yellow]Warning: Error refreshing token: {str(e)}[/yellow]")
                console.print("[yellow]Will attempt to create new credentials...[/yellow]")
                creds = None
        
        # Check if client_secrets.json exists, if not create mock credentials
        if not os.path.exists(CLIENT_SECRETS_FILE):
            console.print(f"[yellow]Client secrets file '{CLIENT_SECRETS_FILE}' not found.[/yellow]")
            console.print("[yellow]Creating mock email response instead...[/yellow]")
            
            # Since we can't build a real service, return a mock response for the email function
            return None  # We'll handle this in the send_email function
        
        # Try to create new credentials from client_secrets.json
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as e:
            console.print(f"[red]Error creating credentials: {str(e)}[/red]")
            console.print("[yellow]Creating mock email response instead...[/yellow]")
            return None  # We'll handle this in the send_email function
        
        # Save credentials for future use
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            console.print("[green]Successfully saved Gmail API credentials[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save token file: {str(e)}[/yellow]")
    
    try:
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        error_msg = f"Failed to build Gmail service: {str(e)}"
        console.print(f"[yellow]{error_msg}[/yellow]")
        console.print("[yellow]Creating mock email response instead...[/yellow]")
        return None  # We'll handle this in the send_email function

# ASCII Value Tool
@mcp.tool()
def get_ascii_values(input_data: Dict[str, Any]) -> TextContent:
    """Convert a string to its ASCII values. This tool is essential for text processing and character analysis.
    
    Args:
        input_data (dict): The input data containing the string to convert
            Format: {"string": "your_string_here"}
            
    Returns:
        TextResponse: A JSON response containing:
            - values: List of ASCII values for each character
            - string: Original input string
            - length: Length of the input string
            
    Example:
        Input: {"string": "ABC"}
        Output: {"values": [65, 66, 67], "string": "ABC", "length": 3}
        
    Error Handling:
        - Returns error response if input string is empty
        - Handles any exceptions during conversion
    """
    console.print("[blue]FUNCTION CALL:[/blue] get_ascii_values()")
    console.print(f"[blue]Input data:[/blue] {input_data}")
    
    try:
        # Handle nested parameters structure if present
        if 'parameters' in input_data and isinstance(input_data['parameters'], dict):
            input_data = input_data['parameters']
        
        # Validate input using Pydantic model
        validated_input = GetAsciiInput(**input_data)
        
        # Convert to ASCII values
        values = [ord(char) for char in validated_input.string]
        
        # Create response
        response = {
            "values": values,
            "string": validated_input.string,
            "length": len(validated_input.string)
        }
        
        console.print(f"[green]ASCII values for '{validated_input.string}':[/green] {values}")
        
        return TextContent(
            type="text",
            text=json.dumps(response)
        )
    except ValidationError as e:
        console.print(f"[red]Validation error in get_ascii_values: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )
    except Exception as e:
        console.print(f"[red]Error in get_ascii_values: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )

# Exponential Sum Tool
@mcp.tool()
def calculate_exponential_sum(input_data: Dict[str, Any]) -> TextContent:
    """Calculate the sum of e raised to each number in a list using high precision decimal arithmetic.
    
    Args:
        input_data (dict): The input data containing a list of numbers
            Format: {"numbers": [num1, num2, ...]}
            
    Returns:
        TextResponse: A JSON response containing:
            - sum: The sum of exponentials (e^num1 + e^num2 + ...)
            - numbers: Original input numbers
            - count: Count of numbers processed
            - scientific_notation: Sum in scientific notation
            
    Example:
        Input: {"numbers": [1, 2, 3]}
        Output: {
            "sum": "40.1711813729",
            "numbers": [1, 2, 3],
            "count": 3,
            "scientific_notation": "4.01711813729e1"
        }
        
    Error Handling:
        - Returns error response if input validation fails
        - Handles any exceptions during calculation
    """
    console.print("[blue]FUNCTION CALL:[/blue] calculate_exponential_sum()")
    console.print(f"[blue]Input data:[/blue] {input_data}")
    
    try:
        # Handle nested parameters structure if present
        if 'parameters' in input_data and isinstance(input_data['parameters'], dict):
            input_data = input_data['parameters']
            
        # Validate input using Pydantic model
        validated_input = CalculateExponentialInput(**input_data)
        
        # Value of e with high precision
        e = Decimal('2.71828182845904523536028747135266249775724709369995')
        
        # Calculate exponentials and sum
        exp_values = []
        total = Decimal(0)
        
        for num in validated_input.numbers:
            exp_value = e ** Decimal(num)
            exp_values.append(str(exp_value))
            total += exp_value
        
        # Create response with detailed information
        response = {
            "sum": str(total),
            "numbers": validated_input.numbers,
            "count": len(validated_input.numbers),
            "scientific_notation": f"{total:e}",
            "details": {
                "individual_exponentials": exp_values,
                "precision": getcontext().prec,
                "e_value_used": str(e)
            }
        }
        
        console.print(f"[green]Exponential sum calculation complete[/green]")
        console.print(f"[green]Sum: {total:e}[/green]")
        
        return TextContent(
            type="text",
            text=json.dumps(response)
        )
        
    except ValidationError as e:
        console.print(f"[red]Validation error in calculate_exponential_sum: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )
    except Exception as e:
        console.print(f"[red]Error in calculate_exponential_sum: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )

# Email Tool
@mcp.tool()
async def send_email(input_data: Dict[str, Any]) -> TextContent:
    """Send an email using Gmail API with optional image attachment.
    
    Args:
        input_data (dict): The input data containing email details
            Format: {
                "to_email": "recipient@example.com",  
                "subject": "Email Subject",  
                "body": "Email Body",  
                "image_path": "optional/path/to/image.jpg"  
            }
            
    Returns:
        TextResponse: A JSON response containing:
            - message_id: ID of the sent message
            - to: Recipient email address
            - subject: Email subject
            - status: "success" or "error"
            
    Example:
        Input: {
            "to_email": "user@example.com",
            "subject": "Test Email",
            "body": "This is a test email."
        }
        
    Error Handling:
        - Returns error response if validation fails
        - Handles exceptions during email sending
    """
    console.print("[blue]FUNCTION CALL:[/blue] send_email()")
    console.print(f"[blue]Input data:[/blue] {input_data}")
    
    try:
        # Handle nested parameters structure if present
        if 'parameters' in input_data and isinstance(input_data['parameters'], dict):
            input_data = input_data['parameters']
            
        # Validate input using Pydantic model
        validated_input = SendEmailInput(**input_data)
        
        # Get Gmail service
        service = get_gmail_service()
        
        # If no service is available, return a mock success response
        if service is None:
            console.print("[yellow]No Gmail service available - sending mock email[/yellow]")
            console.print(f"[green]Mock email would be sent to: {validated_input.to_email}[/green]")
            console.print(f"[green]Subject: {validated_input.subject}[/green]")
            console.print(f"[green]Body: {validated_input.body[:100]}...[/green]")
            
            # Generate a fake message ID
            import uuid
            message_id = f"mock-{str(uuid.uuid4())}"
            
            # Return a success response with mock data
            response = {
                "message_id": message_id,
                "to": validated_input.to_email,
                "subject": validated_input.subject,
                "status": "success",
                "note": "This is a mock email response since no Gmail credentials are available"
            }
            
            return TextContent(
                type="text",
                text=json.dumps(response)
            )
        
        # Create message
        message = MIMEMultipart()
        message['to'] = validated_input.to_email
        message['subject'] = validated_input.subject
        
        # Attach body
        msg = MIMEText(validated_input.body, 'html')
        message.attach(msg)
        
        # Attach image if provided
        if validated_input.image_path:
            if os.path.exists(validated_input.image_path):
                with open(validated_input.image_path, 'rb') as img_file:
                    img = MIMEImage(img_file.read())
                    img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(validated_input.image_path))
                    message.attach(img)
                console.print(f"[green]Attached image: {validated_input.image_path}[/green]")
            else:
                console.print(f"[yellow]Warning: Image file not found: {validated_input.image_path}[/yellow]")
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        send_message = service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        message_id = send_message['id']
        
        console.print(f"[green]Email sent successfully to {validated_input.to_email}[/green]")
        console.print(f"[green]Message ID: {message_id}[/green]")
        
        # Create success response
        response = {
            "message_id": message_id,
            "to": validated_input.to_email,
            "subject": validated_input.subject,
            "status": "success"
        }
        
        return TextContent(
            type="text",
            text=json.dumps(response)
        )
        
    except ValidationError as e:
        console.print(f"[red]Validation error in send_email: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )
    except Exception as e:
        console.print(f"[red]Error in send_email: {str(e)}[/red]")
        return TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "status": "error",
                "input_received": input_data
            })
        )

# Reasoning Tool
@mcp.tool()
def show_reasoning(input_data: dict) -> TextResponse:
    """Display a structured reasoning process with confidence levels for each step.
    This tool helps visualize the decision-making process and validate the agent's thinking.
    
    Args:
        input_data (dict): The input data containing reasoning steps
            Format: {
                "steps": [
                    {
                        "description": "Description of step",
                        "type": "verification",
                        "confidence": 0.9
                    }
                ]
            }
                
    Returns:
        TextResponse: A JSON response confirming the display of reasoning
        
    Example:
        Input: {
            "steps": [
                {"description": "Analyzing email format", "type": "verification", "confidence": 0.9},
                {"description": "Checking content length", "type": "validation", "confidence": 0.8}
            ]
        }
        Output: {"status": "success", "message": "Reasoning shown"}
        
    Error Handling:
        - Validates confidence values
        - Ensures all required fields are present
    """
    console.print("[blue]FUNCTION CALL:[/blue] show_reasoning()")
    try:
        # Validate input using Pydantic model
        validated_input = ShowReasoningInput(**input_data)
        
        for i, step in enumerate(validated_input.steps, 1):
            if isinstance(step, dict):
                step = ReasoningStep(**step)
            console.print(Panel(
                f"{step.description}",
                title=f"Step {i} - {step.type} (Confidence: {step.confidence:.2f})",
                border_style="cyan"
            ))
        return TextResponse(
            content=TextContent(
                type="text",
                text="Reasoning shown"
            )
        )
    except ValidationError as e:
        console.print(f"[red]Validation error in show_reasoning: {str(e)}[/red]")
        return TextResponse(
            content=TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "status": "error"
                })
            )
        )
    except Exception as e:
        console.print(f"[red]Error in show_reasoning: {str(e)}[/red]")
        return TextResponse(
            content=TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "status": "error"
                })
            )
        )

# Consistency Check Tool
@mcp.tool()
def check_consistency(input_data: CheckConsistencyInput) -> TextResponse:
    """Analyze a sequence of steps for logical consistency and potential issues.
    This tool performs comprehensive validation of the agent's actions and decisions.
    
    Args:
        input_data (CheckConsistencyInput): The input data containing steps to analyze
            Format: {
                "steps": [
                    "FUNCTION_CALL: get_ascii_values('ABC')",
                    "FUNCTION_CALL: calculate_exponential_sum([65, 66, 67])"
                ]
            }
            
    Returns:
        TextResponse: A JSON response containing:
            - consistency_score: Overall consistency score (0-100)
            - issues: List of critical issues found
            - warnings: List of potential warnings
            - insights: List of analysis insights
            
    Example:
        Input: {
            "steps": [
                "FUNCTION_CALL: get_ascii_values('ABC')",
                "FUNCTION_CALL: calculate_exponential_sum([65, 66, 67])"
            ]
        }
        Output: {
            "consistency_score": 95.0,
            "issues": [],
            "warnings": ["Step 2: Large numbers might cause overflow"],
            "insights": ["Steps follow logical sequence"]
        }
        
    Error Handling:
        - Validates step format
        - Handles parsing errors
        - Manages calculation errors
    """
    console.print("[blue]FUNCTION CALL:[/blue] check_consistency()")
    
    try:
        # Create a table for step analysis
        table = Table(
            title="Step-by-Step Consistency Analysis",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Step", style="cyan")
        table.add_column("Expression", style="blue")
        table.add_column("Checks", style="yellow")

        issues = []
        warnings = []
        insights = []
        previous = None
        
        for i, step in enumerate(input_data.steps, 1):
            checks = []
            
            # 1. Basic Format Check
            if not step.strip():
                issues.append(f"Step {i}: Empty step")
                checks.append("[red] Empty step[/red]")
            else:
                checks.append("[green] Format valid[/green]")

            # 2. Dependency Analysis
            if previous:
                if str(previous) in step:
                    checks.append("[green] Uses previous result[/green]")
                    insights.append(f"Step {i} builds on step {i-1}")
                else:
                    checks.append("[blue]○ Independent step[/blue]")

            # 3. Pattern Analysis
            if "FUNCTION_CALL" in step:
                checks.append("[green] Valid function call[/green]")
                
                # Email-specific checks
                if "send_email" in step:
                    try:
                        step_data = json.loads(step)
                        params = step_data.get("parameters", {})
                        
                        # Check email format
                        if not re.match(r"[^@]+@[^@]+\.[^@]+", params.get("to_email", "")):
                            issues.append(f"Step {i}: Invalid email format")
                            checks.append("[red] Invalid email format[/red]")
                            
                        # Check subject length
                        subject = params.get("subject", "")
                        if len(subject) > 100:
                            warnings.append(f"Step {i}: Subject too long ({len(subject)} chars)")
                            checks.append("[yellow] Subject too long[/yellow]")
                            
                        # Check body length
                        body = params.get("body", "")
                        if len(body) > 10000:
                            warnings.append(f"Step {i}: Body too long ({len(body)} chars)")
                            checks.append("[yellow] Body too long[/yellow]")
                            
                    except json.JSONDecodeError:
                        warnings.append(f"Step {i}: Could not parse function call")
                        checks.append("[yellow] Parse error[/yellow]")
                        
            elif "FINAL_ANSWER" in step:
                checks.append("[green] Valid final answer[/green]")
            else:
                warnings.append(f"Step {i}: Unrecognized format")
                checks.append("[yellow]! Format warning[/yellow]")

            # Add row to table
            table.add_row(
                f"Step {i}",
                step,
                "\n".join(checks)
            )
            
            previous = step

        # Display Analysis
        console.print("\n[bold cyan]Consistency Analysis Report[/bold cyan]")
        console.print(table)

        if issues:
            console.print(Panel(
                "\n".join(f"[red]• {issue}[/red]" for issue in issues),
                title="Critical Issues",
                border_style="red"
            ))

        if warnings:
            console.print(Panel(
                "\n".join(f"[yellow]• {warning}[/yellow]" for warning in warnings),
                title="Warnings",
                border_style="yellow"
            ))

        if insights:
            console.print(Panel(
                "\n".join(f"[blue]• {insight}[/blue]" for insight in insights),
                title="Analysis Insights",
                border_style="blue"
            ))

        # Final Consistency Score
        total_checks = len(input_data.steps) * 3  # 3 types of checks per step
        passed_checks = total_checks - (len(issues) * 2 + len(warnings))
        consistency_score = (passed_checks / total_checks) * 100

        console.print(Panel(
            f"[bold]Consistency Score: {consistency_score:.1f}%[/bold]\n" +
            f"Passed Checks: {passed_checks}/{total_checks}\n" +
            f"Critical Issues: {len(issues)}\n" +
            f"Warnings: {len(warnings)}\n" +
            f"Insights: {len(insights)}",
            title="Summary",
            border_style="green" if consistency_score > 80 else "yellow" if consistency_score > 60 else "red"
        ))

        return TextResponse(
            content=TextContent(
                type="text",
                text=str(ConsistencyResult(
                    consistency_score=consistency_score,
                    issues=issues,
                    warnings=warnings,
                    insights=insights
                ).dict())
            )
        )
    except Exception as e:
        console.print(f"[red]Error in consistency check: {str(e)}[/red]")
        return TextResponse(
            content=TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )
        )

if __name__ == "__main__":
    # Check if running with mcp dev command
    print("STARTING")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()  # Run without transport for dev server
    else:
        mcp.run(transport="stdio")  # Run with stdio for direct execution