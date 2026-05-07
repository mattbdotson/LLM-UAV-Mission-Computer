import requests
from typing import Optional
from backends.base import InferenceBackend

class VILABackend(InferenceBackend):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        print(f"VILABackend initialized: {self.url}")

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 image_b64: Optional[str] = None) -> str:
        payload = {
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False
        }
        if image_b64:
            payload["image"] = image_b64

        response = requests.post(
            f"{self.url}/generate",
            json=payload,
            timeout=120
        )
        return response.json()["response"]

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{self.url}/health", timeout=3)
            return r.status_code == 200
        except:
            return False

    def get_name(self) -> str:
        return "VILA 1.5-3B"