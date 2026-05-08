import requests
from typing import Optional
from backends.base import InferenceBackend

class LlamaCppBackend(InferenceBackend):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}/v1"
        print(f"LlamaCppBackend initialized: {self.url}")

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 image_b64: Optional[str] = None) -> str:
        has_image = image_b64 is not None and len(image_b64) > 0

        if has_image:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_prompt
                    }
                ]}
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

        payload = {
            "model": "gemma4-e2b",
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.1
        }

        print(f"[LlamaCpp] Sending request — image included: {has_image}, image size: {len(image_b64) if has_image else 0} bytes")
        response = requests.post(
            f"{self.url}/chat/completions",
            json=payload,
            timeout=120
        )
        message = response.json()["choices"][0]["message"]
        reasoning = message.get("reasoning_content")
        if reasoning:
            print(f"[THINKING] {reasoning}")
        return message["content"]

    def health_check(self) -> bool:
        try:
            r = requests.get(f"http://{self.host}:{self.port}/health", timeout=3)
            return r.status_code == 200
        except:
            return False

    def get_name(self) -> str:
        return "Gemma 4 E2B (llama.cpp)"
