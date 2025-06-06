# basic import 
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
from typing import Any, Tuple

# instantiate an MCP server client
mcp = FastMCP("Calculator")

# Global flag to track if Preview is already running
preview_is_running = False
preview_blank_image_path = None

# Gmail OAuth2 configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

def get_gmail_service():
    """Get Gmail service using OAuth2 credentials."""
    creds = None
    
    # Load token from file if it exists
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as token:
            creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Create flow from client secrets
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

# DEFINE TOOLS

#addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together.
    
    Args:
        a (int): First number to add
        b (int): Second number to add
        
    Returns:
        int: The sum of a and b
        
    Example:
        add(5, 3) -> 8
    """
    print("CALLED: add(a: int, b: int) -> int:")
    return int(a + b)

@mcp.tool()
def add_list(l: list) -> int:
    """Add all numbers in a list together.
    
    Args:
        l (list): List of numbers to sum
        
    Returns:
        int: The sum of all numbers in the list
        
    Example:
        add_list([1, 2, 3, 4, 5]) -> 15
    """
    print("CALLED: add_list(l: list) -> int:")
    return sum(l)

# subtraction tool
@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract second number from first number.
    
    Args:
        a (int): First number (minuend)
        b (int): Second number (subtrahend)
        
    Returns:
        int: The difference between a and b
        
    Example:
        subtract(10, 3) -> 7
    """
    print("CALLED: subtract(a: int, b: int) -> int:")
    return int(a - b)

# multiplication tool
@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together.
    
    Args:
        a (int): First number
        b (int): Second number
        
    Returns:
        int: The product of a and b
        
    Example:
        multiply(4, 6) -> 24
    """
    print("CALLED: multiply(a: int, b: int) -> int:")
    return int(a * b)

#  division tool
@mcp.tool() 
def divide(a: int, b: int) -> float:
    """Divide first number by second number.
    
    Args:
        a (int): First number (dividend)
        b (int): Second number (divisor)
        
    Returns:
        float: The quotient of a divided by b
        
    Example:
        divide(15, 3) -> 5.0
    """
    print("CALLED: divide(a: int, b: int) -> float:")
    return float(a / b)

# power tool
@mcp.tool()
def power(a: int, b: int) -> int:
    """Calculate a raised to the power of b.
    
    Args:
        a (int): Base number
        b (int): Exponent
        
    Returns:
        int: a raised to the power of b
        
    Example:
        power(2, 3) -> 8
    """
    print("CALLED: power(a: int, b: int) -> int:")
    return int(a ** b)

# square root tool
@mcp.tool()
def sqrt(a: int) -> float:
    """Calculate the square root of a number.
    
    Args:
        a (int): Number to find square root of
        
    Returns:
        float: The square root of a
        
    Example:
        sqrt(16) -> 4.0
    """
    print("CALLED: sqrt(a: int) -> float:")
    return float(a ** 0.5)

# cube root tool
@mcp.tool()
def cbrt(a: int) -> float:
    """Calculate the cube root of a number.
    
    Args:
        a (int): Number to find cube root of
        
    Returns:
        float: The cube root of a
        
    Example:
        cbrt(27) -> 3.0
    """
    print("CALLED: cbrt(a: int) -> float:")
    return float(a ** (1/3))

# factorial tool
@mcp.tool()
def factorial(a: int) -> int:
    """Calculate the factorial of a number (n!).
    
    Args:
        a (int): Number to calculate factorial of
        
    Returns:
        int: The factorial of a
        
    Example:
        factorial(5) -> 120
    """
    print("CALLED: factorial(a: int) -> int:")
    return int(math.factorial(a))

# log tool
@mcp.tool()
def log(a: int) -> float:
    """Calculate the natural logarithm of a number (ln).
    
    Args:
        a (int): Number to calculate natural log of
        
    Returns:
        float: The natural logarithm of a
        
    Example:
        log(2.718281828459045) -> 1.0
    """
    print("CALLED: log(a: int) -> float:")
    return float(math.log(a))

# remainder tool
@mcp.tool()
def remainder(a: int, b: int) -> int:
    """Calculate the remainder when a is divided by b.
    
    Args:
        a (int): First number (dividend)
        b (int): Second number (divisor)
        
    Returns:
        int: The remainder when a is divided by b
        
    Example:
        remainder(17, 5) -> 2
    """
    print("CALLED: remainder(a: int, b: int) -> int:")
    return int(a % b)

# sin tool
@mcp.tool()
def sin(a: int) -> float:
    """Calculate the sine of an angle in radians.
    
    Args:
        a (int): Angle in radians
        
    Returns:
        float: The sine of the angle
        
    Example:
        sin(0) -> 0.0
    """
    print("CALLED: sin(a: int) -> float:")
    return float(math.sin(a))

# cos tool
@mcp.tool()
def cos(a: int) -> float:
    """Calculate the cosine of an angle in radians.
    
    Args:
        a (int): Angle in radians
        
    Returns:
        float: The cosine of the angle
        
    Example:
        cos(0) -> 1.0
    """
    print("CALLED: cos(a: int) -> float:")
    return float(math.cos(a))

# tan tool
@mcp.tool()
def tan(a: int) -> float:
    """Calculate the tangent of an angle in radians.
    
    Args:
        a (int): Angle in radians
        
    Returns:
        float: The tangent of the angle
        
    Example:
        tan(0) -> 0.0
    """
    print("CALLED: tan(a: int) -> float:")
    return float(math.tan(a))

# mine tool
@mcp.tool()
def mine(a: int, b: int) -> int:
    """Subtract twice the second number from the first number.
    
    Args:
        a (int): First number
        b (int): Second number to subtract twice
        
    Returns:
        int: The result of a - b - b
        
    Example:
        mine(10, 2) -> 6
    """
    print("CALLED: mine(a: int, b: int) -> int:")
    return int(a - b - b)

@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    """Create a thumbnail from an image file.
    
    Args:
        image_path (str): Path to the input image file
        
    Returns:
        Image: Thumbnail image (100x100 pixels)
        
    Example:
        create_thumbnail("input.jpg") -> Image object
    """
    print("CALLED: create_thumbnail(image_path: str) -> Image:")
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")

@mcp.tool()
def get_ascii_values(string: str) -> list[int]:
    """Convert a string to its ASCII values. This is the ONLY function to use for ASCII value conversion.
    
    IMPORTANT: The function name must be exactly 'get_ascii_values' (plural).
    Common mistakes to avoid:
    - ❌ get_ascii_value (singular)
    - ❌ calculate_ascii_value
    - ❌ ascii_value
    - ❌ get_ascii
    
    Args:
        string (str): Input string to convert to ASCII values
        
    Returns:
        list[int]: List of ASCII values for each character in the string
        
    Examples:
        # Correct usage:
        get_ascii_values("ABC") -> [65, 66, 67]
        get_ascii_values("HOME") -> [72, 79, 77, 69]
        
        # Incorrect usage (will fail):
        get_ascii_value("ABC")  # ❌ Wrong: singular form
        calculate_ascii_value("ABC")  # ❌ Wrong: wrong function name
        ascii_value("ABC")  # ❌ Wrong: wrong function name
    """
    print("CALLED: get_ascii_values(string: str) -> list[int]:")
    return [int(ord(char)) for char in string]

class JsonValidator:
    """JSON validation helper for tool responses"""
    
    @staticmethod
    def create_response(is_valid: bool, details: str, data: Any = None) -> dict:
        """Create a standardized JSON response."""
        response = {
            "content": [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "is_valid": is_valid,
                        "details": details,
                        "data": data
                    })
                )
            ]
        }
        return response

    @staticmethod
    def validate_email_params(to_email: str, subject: str, body: str) -> Tuple[bool, str]:
        """Validate email parameters."""
        if not to_email:
            return False, "Email recipient is required"
        if not subject:
            return False, "Email subject is required"
        if not body:
            return False, "Email body is required"
        return True, "Email parameters valid"

    @staticmethod
    def validate_calculation_params(numbers: list) -> Tuple[bool, str]:
        """Validate calculation parameters."""
        if not isinstance(numbers, list):
            return False, "Expected list of numbers"
        if not all(isinstance(x, (int, float)) for x in numbers):
            return False, "All values must be numbers"
        return True, "Calculation parameters valid"

# Update the send_email tool to use JSON validation
@mcp.tool()
async def send_email(to_email: str, subject: str, body: str, image_path: str = None) -> dict:
    """Send an email using Gmail API with OAuth2 authentication.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body text
        image_path (str, optional): Path to image file to attach
        
    Returns:
        dict: JSON response with status and details
    """
    try:
        # Validate parameters
        is_valid, msg = JsonValidator.validate_email_params(to_email, subject, body)
        if not is_valid:
            return JsonValidator.create_response(False, msg)
        
        # Get Gmail service
        service = get_gmail_service()
        
        # Create message
        msg = MIMEMultipart()
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Add image if provided
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_path))
                msg.attach(img)
        
        # Convert and send message
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        message = {'raw': raw_message}
        result = service.users().messages().send(userId='me', body=message).execute()
        
        return JsonValidator.create_response(
            True,
            "Email sent successfully",
            {"message_id": result.get('id')}
        )
        
    except Exception as e:
        return JsonValidator.create_response(
            False,
            f"Error sending email: {str(e)}"
        )

@mcp.tool()
def verify_email_format(email: str) -> dict:
    """Verify if an email address is properly formatted.
    
    Args:
        email (str): Email address to verify
        
    Returns:
        dict: Verification result with status and details
    """
    import re
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(email_regex, email))
    
    return {
        "content": [
            TextContent(
                type="text",
                text=json.dumps({
                    "is_valid": is_valid,
                    "details": "Email format is valid" if is_valid else "Invalid email format"
                })
            )
        ]
    }

@mcp.tool()
def verify_calculation(value: float, expected_range: list) -> dict:
    """Verify if a calculation result is within expected range.
    
    Args:
        value (float): Value to verify
        expected_range (list): List of [min, max] values
        
    Returns:
        dict: Verification result with status and details
    """
    min_val, max_val = expected_range
    is_valid = min_val <= value <= max_val
    
    return {
        "content": [
            TextContent(
                type="text",
                text=json.dumps({
                    "is_valid": is_valid,
                    "details": f"Value {value} is within range [{min_val}, {max_val}]" if is_valid 
                              else f"Value {value} is outside range [{min_val}, {max_val}]"
                })
            )
        ]
    }

@mcp.tool()
def verify_ascii_values(values: list) -> dict:
    """Verify if all values in a list are valid ASCII values.
    
    Args:
        values (list): List of values to verify
        
    Returns:
        dict: Verification result with status and details
    """
    is_valid = all(isinstance(x, int) and 0 <= x <= 127 for x in values)
    invalid_values = [x for x in values if not (isinstance(x, int) and 0 <= x <= 127)]
    
    return {
        "content": [
            TextContent(
                type="text",
                text=json.dumps({
                    "is_valid": is_valid,
                    "details": "All values are valid ASCII codes" if is_valid 
                              else f"Invalid ASCII values found: {invalid_values}"
                })
            )
        ]
    }

@mcp.tool()
def verify_email_content(subject: str, body: str) -> dict:
    """Verify email content for common issues.
    
    Args:
        subject (str): Email subject
        body (str): Email body
        
    Returns:
        dict: Verification result with status and details
    """
    issues = []
    
    # Check subject
    if not subject:
        issues.append("Subject is empty")
    elif len(subject) > 100:
        issues.append("Subject is too long (max 100 chars)")
        
    # Check body
    if not body:
        issues.append("Body is empty")
    elif len(body) > 5000:
        issues.append("Body is too long (max 5000 chars)")
        
    is_valid = len(issues) == 0
    
    return {
        "content": [
            TextContent(
                type="text",
                text=json.dumps({
                    "is_valid": is_valid,
                    "details": "Content is valid" if is_valid else f"Content issues: {issues}"
                })
            )
        ]
    }

# Update the calculate_exponential_sum tool to use JSON validation
@mcp.tool()
def calculate_exponential_sum(numbers: list) -> dict:
    """Calculate the sum of e raised to each number in the input list.
    
    Args:
        numbers (list): List of numbers to calculate exponential sum for
        
    Returns:
        dict: JSON response with result and validation
    """
    try:
        # Validate parameters
        is_valid, msg = JsonValidator.validate_calculation_params(numbers)
        if not is_valid:
            return JsonValidator.create_response(False, msg)
        
        # Calculate result
        result = sum(math.exp(i) for i in numbers)
        
        return JsonValidator.create_response(
            True,
            "Calculation successful",
            {"result": result}
        )
        
    except Exception as e:
        return JsonValidator.create_response(
            False,
            f"Calculation error: {str(e)}"
        )

@mcp.tool()
def generate_fibonacci_sequence(n: int) -> list:
    """Generate the first n numbers in the Fibonacci sequence.
    
    Args:
        n (int): Number of Fibonacci numbers to generate
        
    Returns:
        list: List of first n Fibonacci numbers
        
    Example:
        generate_fibonacci_sequence(5) -> [0, 1, 1, 2, 3]
    """
    print("CALLED: generate_fibonacci_sequence(n: int) -> list:")
    if n <= 0:
        return []
    fib_sequence = [0, 1]
    for _ in range(2, n):
        fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
    return fib_sequence[:n]

@mcp.tool()
async def draw_rectangle(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw a rectangle in Preview from (x1,y1) to (x2,y2).
    
    Args:
        x1 (int): Starting x-coordinate
        y1 (int): Starting y-coordinate
        x2 (int): Ending x-coordinate
        y2 (int): Ending y-coordinate
        
    Returns:
        dict: Status message about the drawing operation
    """
    global preview_is_running, preview_blank_image_path, final_image_path
    
    try:
        # Print a visualization of the rectangle to the console
        print("\n===== RECTANGLE VISUALIZATION =====")
        print(f"Rectangle drawn from ({x1},{y1}) to ({x2},{y2})")
        
        # Calculate dimensions
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        print(f"Width: {width}, Height: {height}")
        
        # Output a simple ASCII rectangle
        print("+" + "-" * (min(width // 10, 30)) + "+")
        for _ in range(min(height // 20, 10)):
            print("|" + " " * (min(width // 10, 30)) + "|")
        print("+" + "-" * (min(width // 10, 30)) + "+")
        print("===================================\n")
        
        # Create a new image with PIL directly
        # Use standard 800x600 canvas with white background
        img = PILImage.new('RGB', (800, 600), color='white')
        
        # Draw the rectangle directly on the image
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        
        # Use the coordinates provided by the client but ensure they're within bounds
        # Ensure coordinates are within the 800x600 canvas
        rect_left = max(10, min(x1, 790))
        rect_top = max(10, min(y1, 590))
        rect_right = max(10, min(x2, 790))
        rect_bottom = max(10, min(y2, 590))
        
        print(f"Using adjusted coordinates: ({rect_left},{rect_top}) to ({rect_right},{rect_bottom})")
        
        # Draw rectangle with a thick black border (5 pixels)
        draw.rectangle([(rect_left, rect_top), (rect_right, rect_bottom)], 
                       outline='black', width=5)
        
        # Save the image to the final output path so we can reuse it
        temp_dir = tempfile.gettempdir()
        final_image_path = os.path.join(temp_dir, "final_result.png")
        img.save(final_image_path)
        
        # Store the rectangle coordinates for text placement
        global rect_center_x, rect_center_y
        rect_center_x = (rect_left + rect_right) // 2
        rect_center_y = (rect_top + rect_bottom) // 2
        
        print(f"Rectangle image created and saved to: {final_image_path}")
        
        # Flag to indicate rectangle was created
        global rectangle_drawn
        rectangle_drawn = True
        
        # If Preview is already running, replace the current image
        if preview_is_running:
            # Close any existing Preview first
            subprocess.run(['osascript', '-e', 'tell application "Preview" to quit'], capture_output=True)
            await asyncio.sleep(1)
        
        # Open the image with Preview
        subprocess.run(['open', '-a', 'Preview', final_image_path])
        await asyncio.sleep(2)
        preview_is_running = True
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Rectangle drawn from ({x1},{y1}) to ({x2},{y2})"
                )
            ]
        }
    except Exception as e:
        print(f"Error in draw_rectangle: {str(e)}")
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error drawing rectangle: {str(e)}"
                )
            ]
        }

# Global variables to track rectangle position and file path
rect_center_x = None
rect_center_y = None
final_image_path = None
rectangle_drawn = False

@mcp.tool()
async def add_text_in_paint(text: str) -> dict:
    """Add text to the Preview canvas. This will place the text inside the previously drawn rectangle.
    
    Args:
        text (str): Text to add to the canvas
        
    Returns:
        dict: Status message about the text addition
    """
    global rectangle_drawn, rect_center_x, rect_center_y, final_image_path, preview_is_running
    
    try:
        # Print the text visualization to the console
        print("\n======= TEXT VISUALIZATION =======")
        print("╔" + "═" * (len(text) + 2) + "╗")
        print("║ " + text + " ║")
        print("╚" + "═" * (len(text) + 2) + "╝")
        print("=================================\n")
        
        if rectangle_drawn and final_image_path:
            # Open the previously created image with rectangle
            img = PILImage.open(final_image_path)
            
            # Add text to the image
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            
            # Try to load a default system font, or fall back to default
            try:
                # Try to use a common system font
                font_path = '/System/Library/Fonts/Helvetica.ttc'
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 36)
                else:
                    # Use default PIL font if Helvetica not available
                    font = ImageFont.load_default()
            except Exception:
                # Fall back to default if any issues loading font
                font = ImageFont.load_default()
            
            # Center the text in the rectangle
            text_width = draw.textlength(text, font=font)
            text_x = rect_center_x - (text_width // 2)
            text_y = rect_center_y - 18  # Approx half the font height
            
            # Draw text with black color
            draw.text((text_x, text_y), text, fill='black', font=font)
            
            # Overwrite the same image file
            img.save(final_image_path)
            
            print(f"Text '{text}' added to image at: {final_image_path}")
            
            # Close Preview and reopen with the updated image
            if preview_is_running:
                # Close any existing Preview first
                subprocess.run(['osascript', '-e', 'tell application "Preview" to quit'], capture_output=True)
                await asyncio.sleep(1)
                
                # Reopen Preview with the updated image
                subprocess.run(['open', '-a', 'Preview', final_image_path])
                await asyncio.sleep(2)
                preview_is_running = True
            else:
                # If Preview wasn't running, just open it
                subprocess.run(['open', '-a', 'Preview', final_image_path])
                await asyncio.sleep(2)
                preview_is_running = True
            
            return {
                "content": [
                    TextContent(
                        type="text",
                        text=f"Text:'{text}' added successfully and displayed in Preview"
                    )
                ]
            }
        else:
            # If no rectangle has been drawn, create a new image with just the text
            img = PILImage.new('RGB', (800, 600), color='white')
            draw = ImageDraw.Draw(img)
            
            # Try to load a default system font, or fall back to default
            try:
                # Try to use a common system font
                font_path = '/System/Library/Fonts/Helvetica.ttc'
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 36)
                else:
                    # Use default PIL font if Helvetica not available
                    font = ImageFont.load_default()
            except Exception:
                # Fall back to default if any issues loading font
                font = ImageFont.load_default()
            
            # Center the text in the image
            text_width = draw.textlength(text, font=font)
            text_x = 400 - (text_width // 2)
            text_y = 300 - 18  # Approx half the font height
            
            # Draw text with black color
            draw.text((text_x, text_y), text, fill='black', font=font)
            
            # Save the image to the final output path
            temp_dir = tempfile.gettempdir()
            final_image_path = os.path.join(temp_dir, "final_result.png")
            img.save(final_image_path)
            
            # Close and reopen Preview with the new image
            if preview_is_running:
                # Close any existing Preview first
                subprocess.run(['osascript', '-e', 'tell application "Preview" to quit'], capture_output=True)
                await asyncio.sleep(1)
                
                # Reopen Preview with the updated image
                subprocess.run(['open', '-a', 'Preview', final_image_path])
                await asyncio.sleep(2)
                preview_is_running = True
            else:
                # If Preview wasn't running, just open it
                subprocess.run(['open', '-a', 'Preview', final_image_path])
                await asyncio.sleep(2)
                preview_is_running = True
            
            print(f"Text '{text}' added to a new image at: {final_image_path}")
            
            return {
                "content": [
                    TextContent(
                        type="text",
                        text=f"Text:'{text}' added to a new image (no rectangle was drawn first)"
                    )
                ]
            }
    except Exception as e:
        print(f"Error in add_text_in_paint: {str(e)}")
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error adding text: {str(e)}"
                )
            ]
        }

@mcp.tool()
async def open_paint() -> dict:
    """Open Preview on macOS with a new blank document.
    
    Returns:
        dict: Status message about the Preview opening operation
    """
    global preview_is_running, final_image_path
    
    try:
        print("Starting open_paint function...")
        
        # Create a blank white image
        img = PILImage.new('RGB', (800, 600), color='white')
        
        # Save to temp directory
        temp_dir = tempfile.gettempdir()
        final_image_path = os.path.join(temp_dir, "final_result.png")
        img.save(final_image_path)
        
        print(f"Blank canvas created at: {final_image_path}")
        
        # Force close any existing Preview to start fresh
        subprocess.run(['osascript', '-e', 'tell application "Preview" to quit'], capture_output=True)
        await asyncio.sleep(1)
        
        # Open the blank image with Preview
        subprocess.run(['open', '-a', 'Preview', final_image_path])
        await asyncio.sleep(2)
        
        # Set flag indicating Preview is running
        preview_is_running = True
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text="Preview opened with a blank canvas"
                )
            ]
        }
    except Exception as e:
        preview_is_running = False
        error_msg = str(e)
        print(f"Error in open_paint: {error_msg}")
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error opening Preview: {error_msg}"
                )
            ]
        }

# DEFINE RESOURCES

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    print("CALLED: get_greeting(name: str) -> str:")
    return f"Hello, {name}!"


# DEFINE AVAILABLE PROMPTS
@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"
    print("CALLED: review_code(code: str) -> str:")


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

if __name__ == "__main__":
    # Check if running with mcp dev command
    print("STARTING")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()  # Run without transport for dev server
    else:
        mcp.run(transport="stdio")  # Run with stdio for direct execution
