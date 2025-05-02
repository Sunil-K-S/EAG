# core/loop.py

import asyncio
from core.context import AgentContext
from core.session import MultiMCP
from core.strategy import decide_next_action
from modules.perception import extract_perception, PerceptionResult
from modules.action import ToolCallResult, parse_function_call
from modules.memory import MemoryItem
import json
import textwrap


class AgentLoop:
    def __init__(self, user_input: str, dispatcher: MultiMCP):
        self.context = AgentContext(user_input)
        self.mcp = dispatcher
        self.tools = dispatcher.get_all_tools()

    def tool_expects_input(self, tool_name: str) -> bool:
        tool = next((t for t in self.tools if getattr(t, "name", None) == tool_name), None)
        if not tool:
            return False
        parameters = getattr(tool, "parameters", {})
        return list(parameters.keys()) == ["input"]

    

    async def run(self) -> str:
        print("[DIAG] Entered AgentLoop.run")
        print("[agent] Starting session:", self.context.session_id)

        try:
            max_steps = self.context.agent_profile.max_steps
            query = self.context.user_input

            for step in range(max_steps):
                print("[DIAG] Top of step loop", step)
                self.context.step = step
                print("[loop] Step", step + 1, "of", max_steps)

                # 🧠 Perception
                print("[DIAG] Before extract_perception")
                perception_raw = await extract_perception(query)
                print("[DIAG] After extract_perception")

                # ✅ Exit cleanly on FINAL_ANSWER
                # ✅ Handle string outputs safely before trying to parse
                if isinstance(perception_raw, str):
                    pr_str = perception_raw.strip()
                    print("[DIAG] Perception is str:", pr_str)
                    # Clean exit if it's a FINAL_ANSWER
                    if pr_str.startswith("FINAL_ANSWER:"):
                        self.context.final_answer = pr_str
                        print("[DIAG] FINAL_ANSWER detected, breaking loop")
                        break

                    # Detect LLM echoing the prompt
                    if "Your last tool produced this result" in pr_str or "Original user task:" in pr_str:
                        print("[perception] ⚠️ LLM likely echoed prompt. No actionable plan.")
                        self.context.final_answer = "FINAL_ANSWER: [no result]"
                        break

                    # Try to decode stringified JSON if it looks valid
                    try:
                        perception_raw = json.loads(pr_str)
                    except json.JSONDecodeError:
                        print("[perception] ⚠️ LLM response was neither valid JSON nor actionable text.")
                        self.context.final_answer = "FINAL_ANSWER: [no result]"
                        break

                # ✅ Try parsing PerceptionResult
                print("[DIAG] Before PerceptionResult parse")
                if isinstance(perception_raw, PerceptionResult):
                    perception = perception_raw
                else:
                    try:
                        # Attempt to parse stringified JSON if needed
                        if isinstance(perception_raw, str):
                            perception_raw = json.loads(perception_raw)
                        perception = PerceptionResult(**perception_raw)
                    except Exception as e:
                        print("[perception] ⚠️ LLM perception failed:", e)
                        print("[perception] Raw output:", perception_raw)
                        break

                print("[perception] Intent:", perception.intent, ", Hint:", perception.tool_hint)

                # 💾 Memory Retrieval
                print("[DIAG] Before memory retrieval")
                retrieved = self.context.memory.retrieve(
                    query=query,
                    top_k=self.context.agent_profile.memory_config["top_k"],
                    type_filter=self.context.agent_profile.memory_config.get("type_filter", None),
                    session_filter=self.context.session_id
                )
                print("[memory] Retrieved", len(retrieved), "memories")

                # 📊 Planning (via strategy)
                print("[DIAG] Before decide_next_action")
                plan = await decide_next_action(
                    context=self.context,
                    perception=perception,
                    memory_items=retrieved,
                    all_tools=self.tools
                )
                print("[plan]", plan)

                if "FINAL_ANSWER:" in plan:
                    # Optionally extract the final answer portion
                    final_lines = [line for line in plan.splitlines() if line.strip().startswith("FINAL_ANSWER:")]
                    if final_lines:
                        self.context.final_answer = final_lines[-1].strip()
                    else:
                        self.context.final_answer = "FINAL_ANSWER: [result found, but could not extract]"
                    print("[DIAG] FINAL_ANSWER in plan, breaking loop")
                    break

                # ⚙️ Tool Execution
                try:
                    print("[DIAG] Before parse_function_call")
                    tool_name, arguments = parse_function_call(plan)
                    print("[DIAG] After parse_function_call", tool_name, arguments)

                    print("[debug] About to call tool:", tool_name, "with arguments:", arguments)

                    if self.tool_expects_input(tool_name):
                        tool_input = {'input': arguments} if not (isinstance(arguments, dict) and 'input' in arguments) else arguments
                    else:
                        tool_input = arguments

                    print("[DIAG] Before mcp.call_tool")
                    response = await self.mcp.call_tool(tool_name, tool_input)
                    print("[DIAG] After mcp.call_tool")

                    # Pretty-print the tool response
                    raw_tool_response = getattr(response, 'content', response)
                    try:
                        # Try to pretty-print as JSON
                        pretty = json.dumps(json.loads(raw_tool_response), indent=2)
                    except Exception:
                        # Fallback: wrap long lines
                        pretty = textwrap.fill(str(raw_tool_response), width=120)
                    print("[debug] Raw tool response:\n", pretty)

                    # ✅ Safe TextContent parsing
                    raw = getattr(response.content, 'text', str(response.content))
                    try:
                        result_obj = json.loads(raw) if raw.strip().startswith("{") else raw
                    except json.JSONDecodeError:
                        result_obj = raw

                    if isinstance(result_obj, dict):
                        result_str = result_obj.get("markdown") or json.dumps(result_obj, indent=2)
                    else:
                        result_str = str(result_obj)
                    # Pretty-print action result
                    if isinstance(result_obj, dict):
                        pretty_action = json.dumps(result_obj, indent=2)
                    else:
                        pretty_action = textwrap.fill(result_str, width=120)
                    print("[action]", tool_name, "→\n", pretty_action)

                    # 🧠 Add memory
                    memory_item = MemoryItem(
                        text=f"{tool_name}({arguments}) → {result_str}",
                        type="tool_output",
                        tool_name=tool_name,
                        user_query=query,
                        tags=[tool_name],
                        session_id=self.context.session_id
                    )
                    self.context.add_memory(memory_item)

                    # 🔁 Next query
                    query = f"""Original user task: {self.context.user_input}

    Your last tool produced this result:

    {result_str}

    If this fully answers the task, return:
    FINAL_ANSWER: your answer

    Otherwise, return the next FUNCTION_CALL."""
                except Exception as e:
                    print("[DIAG] Exception in tool execution block:", e)
                    print("[error] Tool execution failed:", e)
                    break

        except Exception as e:
            print("[DIAG] Exception in outer try block:", e)
            print("[agent] Session failed:", e)
            self.context.final_answer = f"FINAL_ANSWER: [error: {e}]"

        print("[DIAG] Exiting AgentLoop.run")
        if not self.context.final_answer or self.context.final_answer.strip() in ["FINAL_ANSWER: [no result]", "[no result]", ""]:
            self.context.final_answer = "FINAL_ANSWER: Task completed."
        return self.context.final_answer or "FINAL_ANSWER: [no result]"


