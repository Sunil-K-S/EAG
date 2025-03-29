from fastmcp import FastMCP
import asyncio
import os
import win32gui
import win32con
import win32api
from pywinauto.application import Application
import time

# Create MCP server client
mcp = FastMCP("DrawingAgent")

@mcp.tool()
async def open_paint():
    """Opens Paint on Windows"""
    try:
        os.startfile("mspaint.exe")
        await asyncio.sleep(2)  # Wait for Paint to open
        return "Paint opened successfully"
    except Exception as e:
        return f"Error opening Paint: {str(e)}"

@mcp.tool()
async def draw_rectangle(x1: int, y1: int, x2: int, y2: int):
    """Draws a rectangle in Paint"""
    try:
        # Find Paint window
        hwnd = win32gui.FindWindow(None, "Untitled - Paint")
        if hwnd:
            # Bring window to front
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            
            # Get window position
            rect = win32gui.GetWindowRect(hwnd)
            x_offset = rect[0]
            y_offset = rect[1]
            
            # Draw rectangle using mouse events
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x1 + x_offset, y1 + y_offset, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, x2 + x_offset, y2 + y_offset, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x2 + x_offset, y2 + y_offset, 0, 0)
            
            return "Rectangle drawn successfully"
        else:
            return "Paint window not found"
    except Exception as e:
        return f"Error drawing rectangle: {str(e)}"

@mcp.tool()
async def add_text_in_paint(text: str, x: int, y: int):
    """Adds text to Paint"""
    try:
        # Find Paint window
        hwnd = win32gui.FindWindow(None, "Untitled - Paint")
        if hwnd:
            # Bring window to front
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.5)
            
            # Get window position
            rect = win32gui.GetWindowRect(hwnd)
            x_offset = rect[0]
            y_offset = rect[1]
            
            # Click at text position
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x + x_offset, y + y_offset, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x + x_offset, y + y_offset, 0, 0)
            time.sleep(0.5)
            
            # Type text
            for char in text:
                win32api.keybd_event(ord(char), 0, 0, 0)
                win32api.keybd_event(ord(char), 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.1)
            
            return "Text added successfully"
        else:
            return "Paint window not found"
    except Exception as e:
        return f"Error adding text: {str(e)}"

# System prompt for the agent
SYSTEM_PROMPT = """You are a drawing agent that can create drawings in Paint. You have access to these tools:
1. open_paint() - Opens Paint application
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
- Always open Paint first before drawing
- Coordinates are relative to the Paint window
- Wait for each operation to complete before starting the next one
- Use reasonable coordinates (e.g., 100-800 for x, 100-600 for y)
"""

# Example usage
if __name__ == "__main__":
    # Start the MCP server
    mcp.run() 