import json
from typing import List, Tuple, Dict, Any
from pydentic_models import EmailResponse
from rich.console import Console
from datetime import datetime

console = Console()

def update_memory(
    prompt: str,
    return_val: Any,
    args: Dict,
    func_name: str,
    mem_update: str,
    conversation_history: List[Dict],
    result: str
) -> Tuple[str, List[Dict]]:
    """Update conversation history and prompt with new information."""
    try:
        # Extract content from email response if applicable
        if isinstance(return_val, EmailResponse):
            try:
                content = json.loads(return_val.content)
                if "text" in content:
                    mem_update = mem_update.replace("{{content}}", content["text"])
            except json.JSONDecodeError:
                mem_update = mem_update.replace("{{content}}", return_val.content)
        
        # Update conversation history with current step
        current_step = {
            "function": func_name,
            "arguments": args,
            "return_value": return_val,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        conversation_history.append(current_step)
        
        # Build state summary
        state_summary = {
            "completed_steps": [step["function"] for step in conversation_history],
            "last_step": func_name,
            "last_result": result,
            "total_steps": len(conversation_history)
        }
        
        # Update prompt with new information and state
        prompt = f"{prompt}\n\nCurrent State:\n{json.dumps(state_summary, indent=2)}\n\nLast Action:\n{mem_update}"
        
        return prompt, conversation_history
        
    except Exception as e:
        console.print(f"[red]Error updating memory: {str(e)}[/red]")
        return prompt, conversation_history 