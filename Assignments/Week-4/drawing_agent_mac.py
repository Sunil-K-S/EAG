from fastmcp import FastMCP
import asyncio
import subprocess
import pyautogui
import time
from PIL import Image
import os

# Create MCP server client
mcp = FastMCP("DrawingAgent")

@mcp.tool()
async def open_paint():
    """Opens Preview on macOS"""
    try:
        # Open Preview with a new blank document
        subprocess.Popen(['open', '-a', 'Preview'])
        await asyncio.sleep(2)  # Wait for Preview to open
        
        # Create a new blank document
        pyautogui.hotkey('command', 'n')
        await asyncio.sleep(1)
        
        # Set the canvas size
        pyautogui.hotkey('command', 'i')
        await asyncio.sleep(0.5)
        pyautogui.write('800')
        pyautogui.press('tab')
        pyautogui.write('600')
        pyautogui.press('return')
        
        return "Preview opened successfully"
    except Exception as e:
        return f"Error opening Preview: {str(e)}"

@mcp.tool()
async def draw_rectangle(x1: int, y1: int, x2: int, y2: int):
    """Draws a rectangle in Preview"""
    try:
        # Select the rectangle tool
        pyautogui.hotkey('command', 'shift', 'r')
        await asyncio.sleep(0.5)
        
        # Draw rectangle
        pyautogui.moveTo(x1, y1)
        pyautogui.mouseDown()
        pyautogui.moveTo(x2, y2)
        pyautogui.mouseUp()
        
        return "Rectangle drawn successfully"
    except Exception as e:
        return f"Error drawing rectangle: {str(e)}"

@mcp.tool()
async def add_text_in_paint(text: str, x: int, y: int):
    """Adds text to Preview"""
    try:
        # Select text tool
        pyautogui.hotkey('command', 'shift', 't')
        await asyncio.sleep(0.5)
        
        # Click at text position
        pyautogui.click(x, y)
        await asyncio.sleep(0.5)
        
        # Type text
        pyautogui.write(text)
        
        return "Text added successfully"
    except Exception as e:
        return f"Error adding text: {str(e)}"

# System prompt for the agent
SYSTEM_PROMPT = """You are a drawing agent that can create drawings in Preview on macOS. You have access to these tools:
1. open_paint() - Opens Preview application
2. draw_rectangle(x1, y1, x2, y2) - Draws a rectangle at the specified coordinates
3. add_text_in_paint(text, x, y) - Adds text at the specified coordinates

Respond with EXACTLY ONE of these formats:
1. FUNCTION_CALL: tool_name|param1,param2,...
2. FINAL_ANSWER: [message]

Example:
FUNCTION_CALL: open_paint|
FUNCTION_CALL: draw_rectangle|100,100,300,200
FUNCTION_CALL: add_text_in_paint|Hello World,200,150
FINAL_ANSWER: [Drawing completed]

Important:
- Always open Preview first before drawing
- Coordinates are relative to the Preview window
- Wait for each operation to complete before starting the next one
- Use reasonable coordinates (e.g., 100-800 for x, 100-600 for y)
"""

# Example usage
if __name__ == "__main__":
    # Start the MCP server
    mcp.run() 