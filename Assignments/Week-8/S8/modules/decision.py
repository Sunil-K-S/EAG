from typing import List, Optional
from modules.perception import PerceptionResult
from modules.memory import MemoryItem
from modules.model_manager import ModelManager
from dotenv import load_dotenv
import google.generativeai as genaigenai
import os
import asyncio
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Optional: import logger if available
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print("[{}] [{}]".format(now, stage), msg)

model = ModelManager()


async def generate_plan(
    perception: PerceptionResult,
    memory_items: List[MemoryItem],
    tool_descriptions: Optional[str] = None,
    step_num: int = 1,
    max_steps: int = 3
) -> str:
    """Generates the next step plan for the agent: either tool usage or final answer."""

    memory_texts = "\n".join("- " + str(m.text) for m in memory_items) or "None"
    tool_context = f"\nYou have access to the following tools:\n{tool_descriptions}" if tool_descriptions else ""

    try:
        print("[DIAG] Before prompt construction in generate_plan")
        prompt = """
You are a reasoning-driven AI agent with access to tools and memory.
Your job is to solve the user's request step-by-step by reasoning through the problem, selecting a tool if needed, and continuing until the FINAL_ANSWER is produced.

Respond in **exactly one line** using one of the following formats:

- FUNCTION_CALL: tool_name|param1=value1|param2=value2
- FINAL_ANSWER: [your final result] *(Not description, but actual final answer)

🧠 Context:
- Step: {step_num} of {max_steps}
- Memory: 
{memory_texts}
{tool_context}

🎯 Input Summary:
- User input: "{user_input}"
- Intent: {intent}
- Entities: {entities}
- Tool hint: {tool_hint}

✅ Examples:
- FUNCTION_CALL: add|a=5|b=3
- FUNCTION_CALL: strings_to_chars_to_int|input.string=INDIA
- FUNCTION_CALL: int_list_to_exponential_sum|input.int_list=[73,78,68,73,65]
- FINAL_ANSWER: [42] → Always mention final answer to the query, not that some other description.

✅ Examples:
- User asks: "What's the relationship between Cricket and Sachin Tendulkar"
  - FUNCTION_CALL: search_documents|query="relationship between Cricket and Sachin Tendulkar"
  - [receives a detailed document]
  - FINAL_ANSWER: [Sachin Tendulkar is widely regarded as the "God of Cricket" due to his exceptional skills, 
  longevity, and impact on the sport in India. He is the leading run-scorer in both Test and ODI cricket, and the 
  first to score 100 centuries in international cricket. His influence extends beyond his statistics, as he is 
  seen as a symbol of passion, perseverance, and a national icon. ]

✅ Multi-step Workflow Examples:
- User asks: "Create a spreadsheet and mail me the top 10 F1 racers."
  - FUNCTION_CALL: search|query="top 10 F1 racers"
  - [receives search results]
  - FUNCTION_CALL: create_spreadsheet|title="Top 10 F1 Racers"|data=[{{"racer": "Max Verstappen"}}, {{"racer": "Lewis Hamilton"}}, ...]
  - [receives spreadsheet link]
  - FUNCTION_CALL: send_email|to_email="user@example.com"|subject="Top 10 F1 Racers Spreadsheet"|body="Here is the link to the spreadsheet: <spreadsheet_link>"
  - FINAL_ANSWER: [Spreadsheet created and emailed.]

---

📏 IMPORTANT Rules:

- Analyze the user's intent and select the most appropriate tools from the list.
- Chain multiple tools if needed to accomplish the user's goal.
- If the user's request can be fulfilled with a single tool, do not add unnecessary steps.
- When transforming data between tools (e.g., from search to spreadsheet), extract the relevant fields (e.g., names, URLs) and pass them as arguments. For example, if you get a search result with a list of F1 racers, extract just the racer names for the spreadsheet.
- Use create_spreadsheet only if the user requests a spreadsheet or tabular data.
- Use send_email only if the user requests to send information via email.
- 🚫 Do NOT invent tools. Use only the tools listed above. Tool description has useage pattern, only use that.
- 📄 If the question may relate to public/factual knowledge (like companies, people, places), use the `search_documents` tool to look for the answer.
- 🧮 If the question is mathematical, use the appropriate math tool.
- 🔁 Analyze that whether you have already got a good factual result from a tool, do NOT search again — summarize and respond with FINAL_ANSWER.
- ❌ NEVER repeat tool calls with the same parameters unless the result was empty. When searching rely on first reponse from tools, as that is the best response probably.
- ❌ NEVER output explanation text — only structured FUNCTION_CALL or FINAL_ANSWER.
- ✅ Use nested keys like `input.string` or `input.int_list`, and square brackets for lists.
- 💡 If no tool fits or you're unsure, end with: FINAL_ANSWER: [unknown]
- ⏳ You have 3 attempts. Final attempt must end with FINAL_ANSWER.
- ⚡️ Always output FUNCTION_CALLs with arguments as valid JSON (double quotes, no trailing commas, lists in square brackets).
- On your final step (step {max_steps}), you MUST output a FINAL_ANSWER summarizing the result for the user, using the results of previous tool calls. If you just sent an email or created a spreadsheet, summarize what was done and include any relevant links or confirmation.
""".format(
            step_num=step_num,
            max_steps=max_steps,
            memory_texts=memory_texts,
            tool_context=tool_context,
            user_input=perception.user_input.replace('{', '{{').replace('}', '}}'),
            intent=perception.intent,
            entities=', '.join(perception.entities),
            tool_hint=perception.tool_hint or 'None'
        )

        raw = (await model.generate_text(prompt)).strip()
        print("[DIAG] LLM output before log:", raw)
        log("plan", f"LLM output: {raw}")
        print("[DIAG] After log call in generate_plan")

        for line in raw.splitlines():
            if line.strip().startswith("FUNCTION_CALL:") or line.strip().startswith("FINAL_ANSWER:"):
                return line.strip()

        return "FINAL_ANSWER: [unknown]"

    except Exception as e:
        print("[DIAG] Exception in generate_plan except block:", e)
        log("plan", f"⚠️ Planning failed: {e}")
        return "FINAL_ANSWER: [unknown]"

