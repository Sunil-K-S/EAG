import asyncio
from rich.console import Console
from pydentic_models import EmailResponse
from pydantic import ValidationError
import json
import os

console = Console()

# Global user preferences cache
_user_preferences = None

def get_cached_preferences():
    """Get user preferences from file, caching them for reuse"""
    global _user_preferences
    
    if _user_preferences is not None:
        return _user_preferences
        
    try:
        # Default preferences
        default_preferences = {
            "language": "en",
            "priority": "high",
            "email_format": "html",
            "verification_level": "standard"
        }
        
        # Try to load preferences from file
        if os.path.exists("preferences.json"):
            with open("preferences.json", "r") as f:
                preferences = json.load(f)
                _user_preferences = preferences
                return preferences
        else:
            # If file doesn't exist, use defaults
            _user_preferences = default_preferences
            return default_preferences
            
    except Exception as e:
        console.print(f"[red]Error loading preferences: {str(e)}[/red]")
        # Return default preferences in case of error
        return default_preferences

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
        
        # Get user preferences for any function that might need them
        preferences = get_cached_preferences()
        
        # Apply user preferences based on function parameters, not function name
        if "to_email" in cleaned_args and "subject" in cleaned_args and "body" in cleaned_args:
            # Apply email format preference
            if "body" in cleaned_args and preferences.get("email_format") == "html":
                # Check if body already has HTML tags
                if not cleaned_args["body"].strip().startswith("<"):
                    # Convert plain text to HTML with styling based on priority
                    priority_colors = {
                        "low": "#999999",
                        "normal": "#333333",
                        "high": "#CC0000"
                    }
                    color = priority_colors.get(preferences.get("priority", "normal"), "#333333")
                    
                    # Create HTML formatted email
                    html_body = f"""
                    <html>
                    <body>
                        <div style="font-family: Arial, sans-serif; color: {color};">
                            <h2>Email Agent Result</h2>
                            <p>{cleaned_args["body"]}</p>
                            <hr>
                            <p style="font-size: 12px; color: #666666;">
                                Sent by Email Agent<br>
                                Language: {preferences.get("language", "en")}<br>
                                Priority: {preferences.get("priority", "normal")}
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    cleaned_args["body"] = html_body
                    console.print("[green]Converted email body to HTML format[/green]")
            
            # Add user language preference to subject if not English
            if "subject" in cleaned_args and preferences.get("language") != "en":
                language_tags = {
                    "fr": "[FR] ",
                    "es": "[ES] ",
                    "de": "[DE] "
                }
                lang_tag = language_tags.get(preferences.get("language"), "")
                if lang_tag and not cleaned_args["subject"].startswith(lang_tag):
                    cleaned_args["subject"] = lang_tag + cleaned_args["subject"]
                    console.print(f"[green]Added language tag to subject: {lang_tag}[/green]")
        
        # MCP tools expect parameters to be wrapped in an input_data field
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