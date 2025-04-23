import re
import json
from rich.console import Console
import time
from typing import Optional, Dict, Tuple, List, Any
import inspect

console = Console()

def decide(problem: str, result: str, console: Console, conversation_history: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Make a decision based on the LLM response and conversation history."""
    console.print("\n[bold cyan]Decision Making State:[/bold cyan]")
    console.print(f"Problem: {problem}")
    console.print(f"Current conversation history length: {len(conversation_history)}")
    
    # Print the raw conversation history for debugging
    console.print(f"[dim]Conversation history: {conversation_history}[/dim]")
    
    # Initialize completed steps list
    completed_steps = []
    
    # Only process conversation history if it's not empty
    if conversation_history:
        for step in conversation_history:
            try:
                # Skip if step is not a dictionary
                if not isinstance(step, dict):
                    console.print(f"[yellow]Warning: Step is not a dictionary: {type(step)}[/yellow]")
                    continue
                
                # Get function name safely
                function_name = None
                if 'function' in step:
                    function_name = step['function']
                
                if not function_name:
                    console.print(f"[yellow]Warning: Missing function name in step: {step}[/yellow]")
                    continue
                
                # Always consider steps as completed if they have a function name
                # This ensures we don't repeat steps
                completed_steps.append({
                    'function': function_name,
                    'result': step.get('result', {})
                })
                console.print(f"[green]Found completed step: {function_name}[/green]")
                
            except Exception as e:
                console.print(f"[red]Error processing history step: {str(e)}[/red]")
                continue
    
    # Log completed steps
    if completed_steps:
        console.print(f"[green]Completed steps: {[step['function'] for step in completed_steps]}[/green]")
    else:
        console.print("[yellow]No completed steps found[/yellow]")
    
    # Get list of completed functions (don't hardcode function names)
    completed_functions = {step['function'] for step in completed_steps}
    console.print(f"[green]Completed functions: {completed_functions}[/green]")

    # Extract JSON from the response
    try:
        # Convert result to string if it's not already
        if not isinstance(result, str):
            result = str(result)
            
        # Try to find JSON in different formats
        json_str = None
        
        # Format 1: FUNCTION_CALL: prefix
        json_start = result.find('FUNCTION_CALL:')
        if json_start != -1:
            json_str = result[json_start + len('FUNCTION_CALL:'):].strip()
            # Ensure the extracted string is valid JSON
            if not json_str.startswith('{'):
                json_str = '{"steps": [' + json_str
            if not json_str.endswith(']}'):
                json_str = json_str + ']}'
            console.print("[dim]Found FUNCTION_CALL format[/dim]")
        
        # Format 2: Direct JSON - look for JSON block in backticks
        if json_str is None and "```json" in result:
            # Extract JSON from markdown code block
            json_blocks = re.findall(r"```json(.*?)```", result, re.DOTALL)
            if json_blocks:
                json_str = json_blocks[0].strip()
                console.print("[dim]Found JSON in code block[/dim]")
        
        # Format 3: Direct JSON - look for { and }
        if json_str is None:
            # Find the first { character and last } character
            json_start = result.find('{')
            json_end = result.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = result[json_start:json_end+1].strip()
                console.print("[dim]Found direct JSON format[/dim]")
        
        if json_str is None:
            console.print("[yellow]No JSON found in response[/yellow]")
            console.print(f"[dim]Result: {result}[/dim]")
            return None, None, None
        
        # Remove markdown formatting if present
        if json_str.startswith('```json'):
            json_str = json_str[7:].strip()
        if json_str.endswith('```'):
            json_str = json_str[:-3].strip()
        
        # Debug the extracted JSON
        console.print(f"[dim]Extracted JSON: {json_str[:100]}...[/dim]")
        
        # Parse the JSON
        data = json.loads(json_str)
        
        if "function" in data:
            function_name = data["function"]
            parameters = data.get("parameters", {})
            
            # Check if this function has already been completed
            if function_name in completed_functions:
                console.print(f"[yellow]Function {function_name} already completed, skipping[/yellow]")
                return None, None, None
            
            # Clean up parameters - remove verification and reasoning if present
            if isinstance(parameters, dict):
                # Remove non-parameter fields
                if "verification" in parameters:
                    parameters.pop("verification")
                if "reasoning" in parameters:
                    parameters.pop("reasoning")
                
                # Handle steps parameter if present (for any function that uses it)
                if "steps" in parameters:
                    # If the steps is not a list of strings, convert it
                    if not isinstance(parameters["steps"], list):
                        console.print("[yellow]steps parameter is not a list, converting[/yellow]")
                        parameters["steps"] = [str(parameters["steps"])]
                    else:
                        # Convert any non-string items in the list to strings
                        # And remove any FUNCTION_CALL: prefixes
                        clean_steps = []
                        for step in parameters["steps"]:
                            # If it's a FUNCTION_CALL format, extract a description
                            if isinstance(step, str) and "FUNCTION_CALL:" in step:
                                # Extract function name and create a proper step description
                                match = re.search(r"FUNCTION_CALL:\s*(\w+)", step)
                                if match:
                                    func_name = match.group(1)
                                    clean_steps.append(f"Step: Used {func_name} function")
                                else:
                                    clean_steps.append("Step: Performed calculation")
                            else:
                                clean_steps.append(str(step))
                        parameters["steps"] = clean_steps
                        console.print(f"[green]Cleaned steps parameter: {clean_steps}[/green]")
                
                # Handle email parameters if present (for any function that uses them)
                if "parameters" in parameters:
                    parameters = parameters["parameters"]
                # Clean up any escaped quotes in the body if present
                if "body" in parameters:
                    parameters["body"] = parameters["body"].replace('\\"', '"')
            
            # Update the logic for constructing the `steps` parameter for `show_reasoning`
            if function_name == "show_reasoning":
                if "steps" in parameters:
                    # Ensure steps is a list of dictionaries
                    clean_steps = []
                    for step in parameters["steps"]:
                        if isinstance(step, dict):
                            clean_steps.append(step)
                        else:
                            # Convert string representation to dictionary
                            try:
                                step_dict = json.loads(step.replace("'", '"'))
                                clean_steps.append(step_dict)
                            except json.JSONDecodeError:
                                console.print(f"[yellow]Invalid step format, skipping: {step}[/yellow]")
                    parameters["steps"] = clean_steps
                    console.print(f"[green]Cleaned steps parameter for show_reasoning: {clean_steps}[/green]")

            # Update the logic for constructing the `steps` parameter for `check_consistency`
            if function_name == "check_consistency":
                if "steps" in parameters:
                    # Ensure steps is a list of descriptive strings
                    clean_steps = []
                    for step in parameters["steps"]:
                        if isinstance(step, str):
                            # If it's a FUNCTION_CALL format, extract a simple description
                            if "FUNCTION_CALL:" in step:
                                # Extract function name and create a proper step description
                                match = re.search(r"FUNCTION_CALL:\s*(\w+)", step)
                                if match:
                                    func_name = match.group(1)
                                    clean_steps.append(f"Executed {func_name} function")
                                else:
                                    clean_steps.append("Performed a function call")
                            else:
                                clean_steps.append(step)
                        else:
                            # Convert non-string steps to descriptive strings
                            clean_steps.append(str(step))
                    parameters["steps"] = clean_steps
                    console.print(f"[green]Cleaned steps parameter for check_consistency: {clean_steps}[/green]")
            
            console.print(f"[green]Processing function call:[/green] {function_name}")
            console.print(f"[blue]Parameters:[/blue] {parameters}")
            
            # Create memory update message
            memory_update = f"Called function {function_name} with parameters {parameters}"
            
            return function_name, parameters, memory_update
        else:
            console.print("[yellow]No function found in JSON[/yellow]")
            console.print(f"[dim]JSON data: {data}[/dim]")
            return None, None, None
            
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing JSON:[/red] {str(e)}")
        console.print(f"[yellow]Problematic JSON:[/yellow] {json_str}")
        return None, None, None
    except Exception as e:
        console.print(f"[red]Error in decision making:[/red] {str(e)}")
        console.print(f"[dim]Exception details: {e}[/dim]")
        return None, None, None 