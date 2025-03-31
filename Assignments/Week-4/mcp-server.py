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

# Global flag to track if Preview is already running
preview_is_running = False
preview_blank_image_path = None

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
        
        # Use fixed coordinates for a large rectangle in the center
        rect_left = 200
        rect_top = 150
        rect_right = 600
        rect_bottom = 450
        
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
