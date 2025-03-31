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

# instantiate an MCP server client
mcp = FastMCP("Calculator")

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

@mcp.tool()
def calculate_exponential_sum(numbers: list) -> float:
    """Calculate the sum of e raised to each number in the input list.
    
    Args:
        numbers (list): List of numbers to calculate exponential sum for
        
    Returns:
        float: The sum of e raised to each number in the list
        
    Example:
        calculate_exponential_sum([0, 1, 2]) -> 4.718281828459045
    """
    print("CALLED: calculate_exponential_sum(numbers: list) -> float:")
    return sum(math.exp(i) for i in numbers)

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
        
    Example:
        draw_rectangle(100, 100, 300, 200) -> {"content": [{"type": "text", "text": "Rectangle drawn from (100,100) to (300,200)"}]}
    """
    try:
        # Select the rectangle tool using keyboard shortcut
        pyautogui.hotkey('command', 'shift', 'r')
        await asyncio.sleep(0.5)
        
        # Draw rectangle
        pyautogui.moveTo(x1, y1)
        pyautogui.mouseDown()
        pyautogui.moveTo(x2, y2)
        pyautogui.mouseUp()
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Rectangle drawn from ({x1},{y1}) to ({x2},{y2})"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error drawing rectangle: {str(e)}"
                )
            ]
        }

@mcp.tool()
async def add_text_in_paint(text: str) -> dict:
    """Add text to the Preview canvas.
    
    Args:
        text (str): Text to add to the canvas
        
    Returns:
        dict: Status message about the text addition
        
    Example:
        add_text_in_paint("Hello World") -> {"content": [{"type": "text", "text": "Text:'Hello World' added successfully"}]}
    """
    try:
        # Select text tool using keyboard shortcut
        pyautogui.hotkey('command', 'shift', 't')
        await asyncio.sleep(0.5)
        
        # Click where to start typing (center of the canvas)
        pyautogui.click(810, 533)
        await asyncio.sleep(0.5)
        
        # Type the text
        pyautogui.write(text)
        await asyncio.sleep(0.5)
        
        # Click to exit text mode
        pyautogui.click(1050, 800)
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Text:'{text}' added successfully"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )
            ]
        }

@mcp.tool()
async def open_paint() -> dict:
    """Open Preview on macOS with a new blank document.
    
    Returns:
        dict: Status message about the Preview opening operation
        
    Example:
        open_paint() -> {"content": [{"type": "text", "text": "Preview opened successfully with a new blank document"}]}
    """
    try:
        # Create a temporary blank image file
        # Create a temporary directory
        temp_dir = tempfile.gettempdir()
        blank_image_path = os.path.join(temp_dir, "blank_canvas.png")
        
        # Create a blank white image
        img = PILImage.new('RGB', (800, 600), color='white')
        img.save(blank_image_path)
        
        # Open the blank image with Preview
        subprocess.Popen(['open', '-a', 'Preview', blank_image_path])
        await asyncio.sleep(2)  # Wait for Preview to open
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text="Preview opened successfully with a new blank document"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error opening Preview: {str(e)}"
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
