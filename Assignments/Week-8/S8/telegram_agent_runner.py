import asyncio
from modules.telegram_tool import TelegramTool
import sys

# Import the agent's main function
import agent


def run_telegram_agent():
    tool = TelegramTool()
    print("[TelegramAgent] Listening for new messages. Ctrl+C to stop.")
    try:
        while True:
            updates = tool.get_updates(timeout=10)
            if updates:
                for update in updates:
                    message = update.get("message")
                    if message and "text" in message:
                        chat_id = message["chat"]["id"]
                        user_input = message["text"]
                        print(f"[Received] {user_input} from chat_id {chat_id}")

                        # Run the agent with the user input and get the response
                        try:
                            response = asyncio.run(agent.main(user_input))
                        except Exception as e:
                            response = f"[Agent Error] {e}"
                        if response:
                            # Clean up FINAL_ANSWER prefix if present
                            if response.strip().startswith("FINAL_ANSWER:"):
                                response = response.replace("FINAL_ANSWER:", "").strip()
                            tool.send_message(chat_id, response)
                            print(f"[Sent] Response to chat_id {chat_id}")
            import time; time.sleep(2)
    except KeyboardInterrupt:
        print("[TelegramAgent] Stopped.")

if __name__ == "__main__":
    run_telegram_agent() 