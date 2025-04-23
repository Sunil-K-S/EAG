import os
import re
import json
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import google.generativeai as genai
import asyncio
from rich.console import Console
from rich.panel import Panel
from pydentic_models import UserPreferences, FunctionCall, FinalAnswer, EmailResponse

console = Console()

async def generate_with_timeout(model, prompt: str, console: Console, timeout: int = 30) -> str:
    """Generate content with timeout handling."""
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: model.generate_content(prompt)
            ),
            timeout=timeout
        )
        return response.text.strip()
    except asyncio.TimeoutError:
        console.print("[red]Timeout while generating response[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error generating response: {str(e)}[/red]")
        return None

async def get_llm_response(model, prompt, console):
    """Get response from LLM with timeout"""
    response = await generate_with_timeout(model, prompt, console)
    if response:
        return response
    return None

async def get_user_preferences() -> UserPreferences:
    """Get user preferences from file or prompt user."""
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
                current_preferences = json.load(f)
                
            # Show current preferences
            console.print(Panel("Current Preferences:", border_style="cyan"))
            for key, value in current_preferences.items():
                console.print(f"[yellow]{key}:[/yellow] {value}")
            
            # Ask if user wants to modify preferences
            modify = console.input("\n[yellow]Do you want to modify these preferences? (yes/no): [/yellow]").lower()
            
            if modify == 'yes':
                console.print(Panel("Please provide new preferences:", border_style="cyan"))
                new_preferences = {
                    "language": console.input("[yellow]Preferred language (en/fr/es): [/yellow]"),
                    "priority": console.input("[yellow]Task priority (low/normal/high): [/yellow]"),
                    "email_format": console.input("[yellow]Email format (plain/html): [/yellow]"),
                    "verification_level": console.input("[yellow]Verification level (basic/standard/strict): [/yellow]")
                }
                
                # Save new preferences
                with open("preferences.json", "w") as f:
                    json.dump(new_preferences, f, indent=4)
                return UserPreferences(**new_preferences)
            else:
                return UserPreferences(**current_preferences)
        else:
            # If file doesn't exist, ask for preferences
            console.print(Panel("No preferences found. Please provide your preferences:", border_style="cyan"))
            
            preferences = {
                "language": console.input("[yellow]Preferred language (en/fr/es): [/yellow]"),
                "priority": console.input("[yellow]Task priority (low/normal/high): [/yellow]"),
                "email_format": console.input("[yellow]Email format (plain/html): [/yellow]"),
                "verification_level": console.input("[yellow]Verification level (basic/standard/strict): [/yellow]")
            }
            
            # Save preferences to file
            with open("preferences.json", "w") as f:
                json.dump(preferences, f, indent=4)
                
            return UserPreferences(**preferences)
            
    except Exception as e:
        console.print(f"[red]Error handling preferences: {str(e)}[/red]")
        # Return default preferences in case of error
        return UserPreferences(**default_preferences)

async def build_prompt(tools_description, problem, user_preferences: UserPreferences):
    system_prompt = f"""You are an advanced email processing agent with mathematical capabilities.
Follow structured reasoning and strict verification for all operations.

User Preferences:
- Language: {user_preferences.language}
- Priority: {user_preferences.priority}
- Email Format: {user_preferences.email_format}
- Verification Level: {user_preferences.verification_level}

Available Tools:
{tools_description}

Task Processing Guidelines:

1. Planning and Analysis:
   - Break down complex tasks into clear steps
   - Show your reasoning and approach
   - Use structured function calls for execution
   - For exponential calculations: e^a + e^b + e^c, NOT e^(a+b+c)
   - Track completed steps and avoid repeating them

2. IMPORTANT FUNCTION CALL FORMAT:
   Your function calls MUST use ONLY the specified parameter names. Extra fields will be ignored. Refer to the tool descriptions for details.

3. When executing an action, your function call MUST be in this format:
   ```json
   {{
     "function": "name_of_function",
     "parameters": {{
       // ONLY include the exact parameters each function needs as listed above
       // DO NOT include other fields like "verification" or "reasoning" inside parameters
     }}
   }}
   ```

4. Response Approach:
   - Wait for each function to complete before proceeding to the next
   - Show reasoning, but keep function parameters simple and exact
   - Track which functions have already been executed
   - Include only the required parameters for each function

5. Error Handling:
   - If a function fails, check the parameters and try again
   - Make sure you're following the exact parameter formats
   - DO NOT include extra fields in the parameters object

6. Example of Correct Function Call:
   ```json
   {{
     "function": "get_ascii_values",
     "parameters": {{
       "string": "INDIA"
     }}
   }}
   ```

7. Example of Incorrect Function Call (DO NOT DO THIS):
   ```json
   {{
     "function": "get_ascii_values",
     "parameters": {{
       "string": "INDIA",
       "verification": {{...}},  // Wrong! This should not be inside parameters
       "reasoning": {{...}}      // Wrong! This should not be inside parameters
     }}
   }}
   ```

Remember to follow the exact parameter names and formats for each function call.
"""
    return f"{system_prompt}\n\nSolve this problem step by step: {problem}" 