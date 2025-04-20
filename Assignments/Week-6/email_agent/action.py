import asyncio
from rich.console import Console
from pydentic_models import EmailResponse
from pydantic import ValidationError
import json

console = Console()

async def act(session, func_name, args):
    """Execute the action using the MCP session with enhanced error handling"""
    try:
        console.print(f"\n[yellow]Executing: {func_name}[/yellow]")
        console.print(f"[blue]Original arguments:[/blue] {args}")
        
        # Clean up args - remove any extra fields that aren't needed
        cleaned_args = {}
        if isinstance(args, dict):
            # Handle different formats from LLM
            if "parameters" in args:
                # If LLM nested parameters
                if isinstance(args["parameters"], dict):
                    cleaned_args = args["parameters"]
                else:
                    cleaned_args = args
            else:
                # Direct parameters
                # Remove known LLM-added fields that aren't actual parameters
                for key, value in args.items():
                    if key not in ["verification", "reasoning"]:
                        cleaned_args[key] = value
        else:
            cleaned_args = args
            
        console.print(f"[blue]Cleaned arguments:[/blue] {cleaned_args}")
        
        # MCP tools expect parameters to be wrapped in an input_data field
        # This is a special requirement of the MCP API
        final_args = {"input_data": cleaned_args}
        console.print(f"[blue]Final arguments for MCP:[/blue] {final_args}")
        
        # Execute the function with properly formatted arguments
        return_val = await session.call_tool(func_name, final_args)
        
        # Pretty print the result
        if hasattr(return_val, 'content') and return_val.content:
            try:
                content_text = return_val.content[0].text
                content = json.loads(content_text)
                console.print(f"[green]Result:[/green] {json.dumps(content, indent=2)}")
            except Exception:
                console.print(f"[green]Result:[/green] {return_val}")
        
        if isinstance(return_val, dict) and "content" in return_val:
            try:
                response = EmailResponse(**return_val)
                console.print(f"[green]Action completed successfully[/green]")
                return response
            except ValidationError as e:
                console.print(f"[red]Invalid response format: {str(e)}[/red]")
                console.print(f"[yellow]Raw response:[/yellow] {return_val}")
                return None
            except Exception as e:
                console.print(f"[red]Error processing response: {str(e)}[/red]")
                return None
            
        return return_val
        
    except asyncio.TimeoutError:
        console.print(f"[red]Timeout while executing {func_name}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error executing {func_name}: {str(e)}[/red]")
        return None 