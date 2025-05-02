import os
import json
import yaml
import requests
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
from modules.telegram_tool import TelegramTool

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"

class ModelManager:
    def __init__(self):
        self.config = json.loads(MODELS_JSON.read_text())
        self.profile = yaml.safe_load(PROFILE_YAML.read_text())

        self.text_model_key = self.profile["llm"]["text_generation"]
        self.model_info = self.config["models"][self.text_model_key]
        self.model_type = self.model_info["type"]

        # ✅ Gemini initialization (new style)
        if self.model_type == "gemini":
            # You can change the model name here if needed
            self.model = genai.GenerativeModel('gemini-2.0-flash')

        # Register tools here
        self.tools = [
            TelegramTool(),
            # Add other tools here as you implement them
        ]

    def get_all_tools(self):
        return self.tools

    async def generate_text(self, prompt: str) -> str:
        if self.model_type == "gemini":
            return self._gemini_generate(prompt)

        elif self.model_type == "ollama":
            return self._ollama_generate(prompt)

        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

    def _gemini_generate(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        # ✅ Safely extract response text
        try:
            return response.text.strip()
        except AttributeError:
            try:
                return response.candidates[0].content.parts[0].text.strip()
            except Exception:
                return str(response)

    def _ollama_generate(self, prompt: str) -> str:
        response = requests.post(
            self.model_info["url"]["generate"],
            json={"model": self.model_info["model"], "prompt": prompt, "stream": False}
        )
        response.raise_for_status()
        return response.json()["response"].strip()
