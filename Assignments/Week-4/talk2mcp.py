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
from fastmcp import FastMCP

# Load environment variables from .env file
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# List available models
# print("Listing available models...")
# for m in genai.list_models():
#     print(f"Model name: {m.name}")
#     print(f"Display name: {m.display_name}")
#     print(f"Description: {m.description}")
#     print("---")

# Use the free model with safety settings
model = genai.GenerativeModel('gemini-2.0-flash-001',  # Using the correct model name from the list
    generation_config={
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 40,
        "max_output_tokens": 2048,
    },
    safety_settings=[
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE"
        }
    ]
)

max_iterations = 6
last_response = None
iteration = 0
iteration_response = []

async def generate_with_timeout(client, prompt, timeout=10):
    """Generate content with a timeout"""
    print("Starting LLM generation...")
    try:
        # Convert the synchronous generate_content call to run in a thread
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: model.generate_content(prompt)
            ),
            timeout=timeout
        )
        print("LLM generation completed")
        return response
    except TimeoutError:
        print("LLM generation timed out!")
        raise
    except Exception as e:
        print(f"Error in LLM generation: {e}")
        raise

def reset_state():
    """Reset all global variables to their initial state"""
    global last_response, iteration, iteration_response
    last_response = None
    iteration = 0
    iteration_response = []

async def main():
    reset_state()  # Reset at the start of main
    print("Starting main execution...")
    try:
        # Create a single MCP server connection
        print("Establishing connection to MCP server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-server.py"]
        )

        async with stdio_client(server_params) as (read, write):
            print("Connection established, creating session...")
            async with ClientSession(read, write) as session:
                print("Session created, initializing...")
                await session.initialize()
                
                # Get available tools
                print("Requesting tool list...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"Successfully retrieved {len(tools)} tools")

                # Create system prompt with available tools
                print("Creating system prompt...")
                print(f"Number of tools: {len(tools)}")
                
                try:
                    # First, let's inspect what a tool object looks like
                    # if tools:
                    #     print(f"First tool properties: {dir(tools[0])}")
                    #     print(f"First tool example: {tools[0]}")
                    
                    tools_description = []
                    for i, tool in enumerate(tools):
                        try:
                            # Get tool properties
                            params = tool.inputSchema
                            desc = getattr(tool, 'description', 'No description available')
                            name = getattr(tool, 'name', f'tool_{i}')
                            
                            # Format the input schema in a more readable way
                            if 'properties' in params:
                                param_details = []
                                for param_name, param_info in params['properties'].items():
                                    param_type = param_info.get('type', 'unknown')
                                    param_details.append(f"{param_name}: {param_type}")
                                params_str = ', '.join(param_details)
                            else:
                                params_str = 'no parameters'

                            tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                            tools_description.append(tool_desc)
                            print(f"Added description for tool: {tool_desc}")
                        except Exception as e:
                            print(f"Error processing tool {i}: {e}")
                            tools_description.append(f"{i+1}. Error processing tool")
                    
                    tools_description = "\n".join(tools_description)
                    print("Successfully created tools description")
                    
                    # Create a simple list of available tool names for quick reference
                    available_tool_names = [tool.name for tool in tools]
                    available_tools_list = ", ".join(available_tool_names)
                    print(f"Available tools list: {available_tools_list}")
                    
                except Exception as e:
                    print(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"
                    available_tools_list = "Error loading tool names"
                
                print("Created system prompt...")
                
                # System prompt for the agent
                SYSTEM_PROMPT = f"""You are an autonomous agent that can perform mathematical calculations and display results using Preview on macOS. You have access to ONLY these specific tools:

{tools_description}

AVAILABLE TOOLS (use ONLY these exact names): {available_tools_list}

Your task is to:
1. Analyze the user's request carefully
2. Plan and print the sequence of tool calls needed to fulfill the request
3. Execute the tools in the correct order
4. Display the final result in Preview

Important Guidelines:
1. Tool Selection:
   - You can ONLY use the tools listed above - no other tools exist
   - NEVER try to use a tool that isn't in the AVAILABLE TOOLS list
   - Read the AVAILABLE TOOLS list carefully and identify tools that match the functionality you need
   - If you need to perform an operation, first check if there's a specialized tool for it
   - Always check the AVAILABLE TOOLS list before making any function calls
   - Use the EXACT function names from the tools list - no variations allowed

2. Response Format:
   You must respond with EXACTLY ONE line in one of these formats (no additional text):
   1. For function calls:
      FUNCTION_CALL: function_name|param1|param2|...
   2. For final answers:
      FINAL_ANSWER: [message]

   IMPORTANT PARAMETER FORMATTING RULES:
   - For arrays, use ONLY the array format directly: [1, 2, 3] and NOT variable assignments like l=[1, 2, 3]
   - Parameters must be raw values without variable names or prefixes

   DO NOT include any explanations or additional text.
   Your entire response should be a single line starting with either FUNCTION_CALL: or FINAL_ANSWER:

3. Best Practices:
   - If you get an "Unknown tool" error, check the AVAILABLE TOOLS list and use the exact function name
   - Do not try to create new tools or use tools that aren't listed
   - For compound operations, see if there's a specialized tool that can do the entire operation at once
   - Look for tools that handle the entire task rather than breaking it into smaller steps

Remember:
- You are autonomous - make decisions about which tools to use and when
- ALWAYS verify function names against the AVAILABLE TOOLS list
- Plan your sequence of operations before executing
- Handle errors gracefully and provide clear feedback
"""

                query = """Find the ASCII values of characters in the word "INDIA", then calculate the sum of exponentials of those ASCII values.

After completing the calculation, display the result visually:
1. Open a blank canvas or document
2. Draw a rectangle on the canvas using coordinates (100, 100) to (700, 500) to frame the result
3. Add the calculated result as text inside the rectangle
4. Finish with a final answer showing the calculation result

Follow these steps in sequence:
- First, get the ASCII values for "INDIA"
- Then calculate the sum of exponentials of those ASCII values
- Open a drawing application
- Draw a rectangle with the coordinates (100, 100, 700, 500)
- Finally, add the calculated result as text inside the rectangle

Make sure to:
- Choose the appropriate functions from the available tools list
- Provide the correct parameters for each function
- Wait for each operation to complete before proceeding to the next
- Format parameters correctly (use arrays in [value1, value2] format, not variable assignments)
"""
                print("Starting iteration loop...")
                
                # Use global iteration variables
                global iteration, last_response
                
                while iteration < max_iterations:
                    print(f"\n--- Iteration {iteration + 1} ---")
                    if last_response is None:
                        current_query = query
                    else:
                        current_query = current_query + "\n\n" + " ".join(iteration_response)
                        current_query = current_query + "  What should I do next?"

                    # Get model's response with timeout
                    print("Preparing to generate LLM response...")
                    prompt = f"{SYSTEM_PROMPT}\n\nQuery: {current_query}"
                    try:
                        response = await generate_with_timeout(model, prompt)
                        response_text = response.text.strip()
                        print(f"LLM Response: {response_text}")
                        
                        # Find the FUNCTION_CALL line in the response
                        for line in response_text.split('\n'):
                            line = line.strip()
                            if line.startswith("FUNCTION_CALL:"):
                                response_text = line
                                break
                        
                    except Exception as e:
                        print(f"Failed to get LLM response: {e}")
                        break


                    if response_text.startswith("FUNCTION_CALL:"):
                        _, function_info = response_text.split(":", 1)
                        parts = [p.strip() for p in function_info.split("|")]
                        func_name, params = parts[0], parts[1:]
                        
                        print(f"\nDEBUG: Raw function info: {function_info}")
                        print(f"DEBUG: Split parts: {parts}")
                        print(f"DEBUG: Function name: {func_name}")
                        print(f"DEBUG: Raw parameters: {params}")
                        
                        try:
                            # Find the matching tool to get its input schema
                            tool = next((t for t in tools if t.name == func_name), None)
                            if not tool:
                                print(f"DEBUG: Available tools: {[t.name for t in tools]}")
                                error_msg = f"Unknown tool: {func_name}. Available tools are: {available_tools_list}"
                                print(f"DEBUG: {error_msg}")
                                raise ValueError(error_msg)

                            print(f"DEBUG: Found tool: {tool.name}")
                            print(f"DEBUG: Tool schema: {tool.inputSchema}")

                            # Prepare arguments according to the tool's input schema
                            arguments = {}
                            schema_properties = tool.inputSchema.get('properties', {})
                            print(f"DEBUG: Schema properties: {schema_properties}")

                            for param_name, param_info in schema_properties.items():
                                if not params:  # Check if we have enough parameters
                                    raise ValueError(f"Not enough parameters provided for {func_name}")
                                    
                                value = params.pop(0)  # Get and remove the first parameter
                                param_type = param_info.get('type', 'string')
                                
                                print(f"DEBUG: Converting parameter {param_name} with value {value} to type {param_type}")
                                
                                # Convert the value to the correct type based on the schema
                                if param_type == 'integer':
                                    arguments[param_name] = int(value)
                                elif param_type == 'number':
                                    arguments[param_name] = float(value)
                                elif param_type == 'array':
                                    # Handle array input
                                    if isinstance(value, str):
                                        value = value.strip('[]').split(',')
                                    arguments[param_name] = [int(x.strip()) for x in value]
                                else:
                                    arguments[param_name] = str(value)

                            print(f"DEBUG: Final arguments: {arguments}")
                            print(f"DEBUG: Calling tool {func_name}")
                            
                            result = await session.call_tool(func_name, arguments=arguments)
                            print(f"DEBUG: Raw result: {result}")
                            
                            # Get the full result content
                            if hasattr(result, 'content'):
                                print(f"DEBUG: Result has content attribute")
                                # Handle multiple content items
                                if isinstance(result.content, list):
                                    iteration_result = [
                                        item.text if hasattr(item, 'text') else str(item)
                                        for item in result.content
                                    ]
                                else:
                                    iteration_result = str(result.content)
                            else:
                                print(f"DEBUG: Result has no content attribute")
                                iteration_result = str(result)
                                
                            print(f"DEBUG: Final iteration result: {iteration_result}")
                            
                            # Format the response based on result type
                            if isinstance(iteration_result, list):
                                result_str = f"[{', '.join(iteration_result)}]"
                            else:
                                result_str = str(iteration_result)
                            
                            iteration_response.append(
                                f"In the {iteration + 1} iteration you called {func_name} with {arguments} parameters, "
                                f"and the function returned {result_str}."
                            )
                            last_response = iteration_result

                        except Exception as e:
                            print(f"DEBUG: Error details: {str(e)}")
                            print(f"DEBUG: Error type: {type(e)}")
                            import traceback
                            traceback.print_exc()
                            iteration_response.append(f"Error in iteration {iteration + 1}: {str(e)}")
                            break

                    elif response_text.startswith("FINAL_ANSWER:"):
                        print("\n=== Agent Execution Complete ===")
                        print(f"Final answer: {response_text}")
                        break

                    iteration += 1

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reset_state()  # Reset at the end of main

if __name__ == "__main__":
    asyncio.run(main())
