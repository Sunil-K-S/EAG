from fastmcp import FastMCP
import asyncio

# Create MCP client
mcp = FastMCP("DrawingAgent")

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

async def run_agent():
    # Task for the agent
    task = """Draw a rectangle and write 'Hello World' inside it in Paint."""
    
    # Initialize conversation
    conversation = []
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        print(f"\n--- Iteration {iteration + 1} ---")
        
        # Build the prompt
        if iteration == 0:
            prompt = f"{SYSTEM_PROMPT}\n\nTask: {task}"
        else:
            prompt = f"{SYSTEM_PROMPT}\n\nTask: {task}\n\nPrevious steps:\n" + "\n".join(conversation)
        
        # Get agent's response
        response = await mcp.chat(prompt)
        print(f"Agent Response: {response}")
        
        # Parse the response
        if response.startswith("FUNCTION_CALL:"):
            # Extract function name and parameters
            _, function_info = response.split(":", 1)
            func_name, params = [x.strip() for x in function_info.split("|", 1)]
            
            # Execute the function
            if func_name == "open_paint":
                result = await mcp.open_paint()
            elif func_name == "draw_rectangle":
                x1, y1, x2, y2 = map(int, params.split(","))
                result = await mcp.draw_rectangle(x1, y1, x2, y2)
            elif func_name == "add_text_in_paint":
                text, x, y = params.split(",")
                x, y = map(int, [x, y])
                result = await mcp.add_text_in_paint(text, x, y)
            
            print(f"Function Result: {result}")
            conversation.append(f"Step {iteration + 1}: Called {func_name} with parameters {params}. Result: {result}")
            
        elif response.startswith("FINAL_ANSWER:"):
            print("\n=== Agent Execution Complete ===")
            break
        
        iteration += 1

if __name__ == "__main__":
    asyncio.run(run_agent()) 