import requests
from typing import Optional
from backends.base import InferenceBackend

class OllamaBackend(InferenceBackend):
    def __init__(self, host: str, port: int, model: str):
        self.host = host
        self.port = port
        self.model = model
        self.url = f"http://{host}:{port}/api/chat"
        print(f"OllamaBackend initialized: {self.url} model={model}")

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 image_b64: Optional[str] = None) -> str:
        message = {"role": "user", "content": user_prompt}
        if image_b64:
            message["images"] = [image_b64]

        payload = {
            "model": self.model,
            "messages": [message],
            "system": system_prompt,
            "stream": False
        }

        response = requests.post(self.url, json=payload, timeout=60)
        return response.json()["message"]["content"]

    def health_check(self) -> bool:
        try:
            r = requests.get(f"http://{self.host}:{self.port}/api/version", timeout=3)
            return r.status_code == 200
        except:
            return False

    def get_name(self) -> str:
        return f"Ollama ({self.model})"