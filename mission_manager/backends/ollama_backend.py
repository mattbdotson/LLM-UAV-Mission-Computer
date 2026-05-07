import requests
from typing import Optional
from backends.base import InferenceBackend

class OllamaBackend(InferenceBackend):
    def __init__(self, host: str, port: int, model: str):
        self.host = host
        self.port = port
        self.model = model
        self.url = f"http://{host}:{port}/api/generate"
        print(f"OllamaBackend initialized: {self.url} model={model}")

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 image_b64: Optional[str] = None) -> str:
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False
        }
        if image_b64:
            payload["images"] = [image_b64]

        response = requests.post(self.url, json=payload, timeout=60)
        return response.json()["response"]

    def health_check(self) -> bool:
        try:
            r = requests.get(f"http://{self.host}:{self.port}/api/version", timeout=3)
            return r.status_code == 200
        except:
            return False

    def get_name(self) -> str:
        return f"Ollama ({self.model})"