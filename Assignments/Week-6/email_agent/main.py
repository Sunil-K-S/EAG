import os
import asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
import json
import time

from perception import get_user_preferences, build_prompt, generate_with_timeout
from memory import update_memory
from decision import decide
from action import act

console = Console()

# Load environment variables and setup Gemini
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Configure the model with specific parameters
model = genai.GenerativeModel(
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

async def main():
    try:
        console.print("\n[cyan]Initializing Email Agent...[/cyan]")
        
        # Initialize conversation history
        conversation_history = []
        console.print("[green]Conversation history initialized[/green]")
        
        # Get user preferences
        user_preferences = await get_user_preferences()
        console.print("[green]User preferences loaded[/green]")
        
        # Initialize MCP connection
        console.print("\n[cyan]Initializing MCP connection...[/cyan]")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                console.print("[green]MCP connection established[/green]")
                
                # Get available tools
                console.print("\n[cyan]Fetching available tools...[/cyan]")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                console.print(f"[green]Found {len(tools)} tools[/green]")
                
                # Extract function names without any hardcoding
                available_functions = [getattr(tool, 'name', f'tool_{i}') for i, tool in enumerate(tools)]
                console.print(f"[green]Available functions: {available_functions}[/green]")
                
                # Create tools description
                tools_description = []
                for i, tool in enumerate(tools):
                    try:
                        params = tool.inputSchema
                        desc = getattr(tool, 'description', 'No description available')
                        name = getattr(tool, 'name', f'tool_{i}')
                        
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
                    except Exception as e:
                        console.print(f"[red]Error processing tool {i}: {e}[/red]")
                        tools_description.append(f"{i+1}. Error processing tool")
                
                tools_description = "\n".join(tools_description)
                console.print("[green]Tools description created[/green]")
                
                # Hardcoded task
                problem = 'Find the ASCII values of characters in the word "INDIA", then calculate the sum of exponentials of those ASCII values. Mail the final answer to me. My email address is "sunilks.eminem@gmail.com"'
                console.print(f"\n[cyan]Task:[/cyan] {problem}")
                
                # Build initial prompt with all required arguments
                console.print("\n[cyan]Building initial prompt...[/cyan]")
                prompt = await build_prompt(tools_description, problem, user_preferences)
                # Add a message to tell the LLM all available functions
                prompt += f"\n\nThe following functions are available to solve this task: {available_functions}"
                console.print("[green]Prompt built successfully[/green]")
                
                # Track completed functions and results
                completed_functions = set()
                failed_functions = set()
                max_iterations = 10  # Prevent infinite loops
                iteration = 0
                
                # Results dictionary
                step_results = {}
                
                while iteration < max_iterations:
                    iteration += 1
                    console.print(f"\n[cyan]Iteration {iteration}/{max_iterations}[/cyan]")
                    
                    try:
                        # Check if all available functions have been attempted
                        remaining_functions = [f for f in available_functions if f not in completed_functions and f not in failed_functions]
                        if not remaining_functions:
                            console.print("\n[green]All available functions have been executed. Task finished![/green]")
                            break
                            
                        # Get LLM response
                        console.print("\n[cyan]Getting LLM response...[/cyan]")
                        response = await generate_with_timeout(model, prompt, console)
                        if not response:
                            console.print("[red]No response from LLM[/red]")
                            break
                            
                        result = response
                        console.print(f"\n[yellow]Assistant:[/yellow] {result}")
                        
                        # Add current state to prompt for next iteration
                        state_update = "\n\nCurrent state:\n"
                        state_update += f"- Available functions: {available_functions}\n"
                        state_update += f"- Completed functions: {list(completed_functions)}\n"
                        state_update += f"- Failed functions: {list(failed_functions)}\n"
                        state_update += f"- Remaining functions: {remaining_functions}\n"
                        
                        # Add any results we've collected to the state
                        if step_results:
                            state_update += "- Results so far:\n"
                            for key, value in step_results.items():
                                state_update += f"  - {key}: {value}\n"
                            
                        # Decide next action
                        console.print("\n[cyan]Deciding next action...[/cyan]")
                        func_name, args, mem_update = decide(problem, result, console, conversation_history)
                        
                        # If no action needed, continue to next iteration
                        if not func_name:
                            console.print("[yellow]No valid function call found, continuing...[/yellow]")
                            prompt += f"\n\nSystem: No valid function was found in your response. Please try again with one of the remaining functions: {remaining_functions}. {state_update}"
                            continue
                            
                        # Validate that the function exists
                        if func_name not in available_functions:
                            console.print(f"[red]Function {func_name} is not available[/red]")
                            prompt += f"\n\nSystem: The function {func_name} is not available. Please use one of these functions: {available_functions}. {state_update}"
                            continue
                            
                        # Check if this function was already executed
                        if func_name in completed_functions:
                            console.print(f"[yellow]Function {func_name} already executed, skipping...[/yellow]")
                            prompt += f"\n\nSystem: The function {func_name} has already been executed successfully. Please proceed to one of these remaining functions: {remaining_functions}. {state_update}"
                            continue
                            
                        # Check if this function previously failed
                        if func_name in failed_functions:
                            console.print(f"[yellow]Function {func_name} previously failed, attempting again...[/yellow]")
                            
                        # Execute action
                        console.print(f"\n[cyan]Executing action: {func_name}[/cyan]")
                        console.print(f"[blue]Arguments: {args}[/blue]")
                        return_val = await act(session, func_name, args)
                        
                        if return_val is None or (hasattr(return_val, 'isError') and return_val.isError):
                            console.print(f"[red]Action failed: {func_name}[/red]")
                            failed_functions.add(func_name)
                            prompt += f"\n\nSystem: The function {func_name} failed to execute properly. Please try again with corrected parameters or use one of these remaining functions: {remaining_functions}. {state_update}"
                            continue
                            
                        # Store result for this step
                        try:
                            if hasattr(return_val, 'content') and return_val.content:
                                # Extract the JSON content if available
                                content_text = return_val.content[0].text
                                content = json.loads(content_text)
                                
                                # Don't rely on function name patterns - store all interesting data
                                # Store values, numbers, and strings that might be useful
                                for key, value in content.items():
                                    result_key = f"{func_name}_{key}"
                                    step_results[result_key] = value
                                    console.print(f"Stored result: {result_key} = {value}")
                                
                                # For calculate_exponential_sum, store exact result for future use
                                if func_name == "calculate_exponential_sum" and "scientific_notation" in content:
                                    step_results["exact_exp_sum"] = content["scientific_notation"]
                                    console.print(f"[green]Stored exact exponential sum: {content['scientific_notation']}[/green]")
                        except Exception as e:
                            console.print(f"[yellow]Warning: Unable to parse result content: {str(e)}[/yellow]")
                            
                        # Mark this function as completed
                        completed_functions.add(func_name)
                        console.print(f"Marked {func_name} as completed")
                        
                        # Update conversation history with the result
                        conversation_history.append({
                            'function': func_name,
                            'parameters': args,
                            'result': return_val,
                            'timestamp': time.time(),
                            'status': 'completed'
                        })
                        console.print("Added %s result to history" % func_name)
                        console.print("Conversation history now has %d entries" % len(conversation_history))
                        
                        # Update memory and prompt
                        console.print("\n[cyan]Updating memory and prompt...[/cyan]")
                        prompt += f"\n\nSystem: {mem_update}. {state_update}"
                        console.print("Memory and prompt updated")
                            
                    except Exception as e:
                        console.print(f"\n[red]Error during execution: {str(e)}[/red]")
                        if "timeout" in str(e).lower():
                            console.print("[yellow]Retrying after timeout...[/yellow]")
                            await asyncio.sleep(1)
                            continue
                        break
                    
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 