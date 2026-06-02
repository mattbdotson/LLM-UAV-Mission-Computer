import re
import requests
import time
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
            "max_tokens": 3000,
            "temperature": 0.1,
            "cache_prompt": False
        }

        print(f"[LlamaCpp] Sending request — image included: {has_image}, image size: {len(image_b64) if has_image else 0} bytes")
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{self.url}/chat/completions",
                    json=payload,
                    timeout=120
                )
                break
            except requests.exceptions.ConnectionError as e:
                if attempt == 0:
                    print(f"[LlamaCpp] Connection error, retrying in 5s: {e}")
                    time.sleep(5)
                else:
                    raise
        message = response.json()["choices"][0]["message"]
        reasoning = message.get("reasoning_content") or ""
        content = message.get("content") or ""
        if reasoning:
            print(f"[THINKING] {reasoning}")
        if not content and reasoning:
            print("[LlamaCpp] WARNING: model produced reasoning but no content — likely ran out of tokens before emitting JSON. Falling back to RTL.")
            return ""
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return match.group(0)
        return content

    def clear_cache(self):
        try:
            r = requests.post(f"http://{self.host}:{self.port}/cache/clear", timeout=5)
            print(f"[LlamaCpp] Cache cleared: {r.status_code}")
        except Exception as e:
            print(f"[LlamaCpp] Cache clear not available: {e}")

    def health_check(self) -> bool:
        try:
            r = requests.get(f"http://{self.host}:{self.port}/health", timeout=3)
            return r.status_code == 200
        except:
            return False

    def get_name(self) -> str:
        return "Gemma 4 E2B (llama.cpp)"
