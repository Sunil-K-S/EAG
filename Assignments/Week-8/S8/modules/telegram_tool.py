import os
import requests
from typing import Optional, Dict, Any
import time

class TelegramTool:
    name = "telegram"
    description = "Send and receive messages via Telegram. Use for user notifications and command input."
    parameters = {
        "chat_id": "ID of the chat to send a message to",
        "text": "Text of the message to send"
    }

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment.")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = None

    def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_updates(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/getUpdates"
        params = {"timeout": timeout}
        if self.last_update_id:
            params["offset"] = self.last_update_id + 1
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") and data.get("result"):
            updates = data["result"]
            if updates:
                self.last_update_id = updates[-1]["update_id"]
                return updates
        return None

    def parse_command(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extracts command and arguments from a Telegram message.
        Returns dict with 'command' and 'args' if found.
        """
        text = message.get("text", "")
        if text.startswith("/"):
            parts = text[1:].split()
            command = parts[0]
            args = parts[1:]
            return {"command": command, "args": args, "chat_id": message["chat"].get("id")}
        return None

# Example tool registry function

def get_telegram_tool():
    return TelegramTool()

# --- Test and polling loop ---

def polling_loop(tool: TelegramTool, poll_interval: int = 3):
    print("[Polling] Listening for new Telegram messages. Press Ctrl+C to stop.")
    try:
        while True:
            updates = tool.get_updates(timeout=10)
            if updates:
                for update in updates:
                    message = update.get("message")
                    if message:
                        print(f"[Received] From chat_id {message['chat']['id']}: {message.get('text')}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("[Polling] Stopped.")

if __name__ == "__main__":
    tool = TelegramTool()
    print("TelegramTool test mode.")
    mode = input("Enter 'send' to send a message, 'poll' to start polling: ").strip().lower()
    if mode == 'send':
        chat_id = input("Enter chat_id: ").strip()
        text = input("Enter message: ").strip()
        resp = tool.send_message(chat_id, text)
        print(f"[Sent] Response: {resp}")
    elif mode == 'poll':
        polling_loop(tool)
    else:
        print("Unknown mode.") 