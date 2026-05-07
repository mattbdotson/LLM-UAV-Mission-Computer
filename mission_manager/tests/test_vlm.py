import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from mapping.map_compositor import MapCompositor
from config.map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET, VLM_IMAGE_SIZE
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

INFERENCE_BACKEND = os.getenv('INFERENCE_BACKEND', 'llamacpp').lower()
LLAMACPP_HOST = os.getenv('LLAMACPP_HOST', 'localhost')
LLAMACPP_PORT = os.getenv('LLAMACPP_PORT', '8080')

if INFERENCE_BACKEND == 'llamacpp':
    HOST = LLAMACPP_HOST
    PORT = LLAMACPP_PORT
else:
    HOST = LLAMACPP_HOST
    PORT = LLAMACPP_PORT

BASE_URL = f"http://{HOST}:{PORT}"
MODEL = "gemma4-e2b"

MISSION_MANAGER_DIR = os.path.join(os.path.dirname(__file__), '..')


def test_health():
    print(f"Testing llama-server health endpoint at {BASE_URL}/health ...")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def test_text_only():
    print(f"\nTesting {MODEL} text-only inference...")
    print("Sending request, this may take up to 3 minutes on first inference...")
    try:
        r = requests.post(f"{BASE_URL}/v1/chat/completions", json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "What is a waypoint in aviation? Answer in one sentence."}],
            "max_tokens": 100
        }, timeout=180)
        print(f"Full raw response: {r.json()}")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()['choices'][0]['message']['content']}")
        return True
    except Exception as e:
        print(f"Text test failed: {e}")
        return False


def test_image_inference():
    print(f"\nTesting {MODEL} image + text inference...")

    tile_path = os.path.join(MISSION_MANAGER_DIR, 'assets', MAP_TILE_PATH)
    compositor = MapCompositor(tile_path, MAP_BOUNDS, vlm_size=VLM_IMAGE_SIZE)
    state = {
        "lat": -35.363,
        "lon": 149.165,
        "heading": 45,
        "alt": 150,
        "airspeed": 22
    }
    image_b64 = compositor.compose(state, MISSION_TARGET)

    print("Sending request, this may take up to 3 minutes on first inference...")
    try:
        r = requests.post(f"{BASE_URL}/v1/chat/completions", json={
            "model": MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": "This is a top-down map. The blue arrow is an aircraft. The red crosshair is a mission target. Where is the aircraft relative to the target? What direction should it fly?"}
            ]}],
            "max_tokens": 200
        }, timeout=180)

        print(f"Full raw response: {r.json()}")
        print(f"Status: {r.status_code}")
        print(f"VLM response: {r.json()['choices'][0]['message']['content']}")

        return True
    except Exception as e:
        print(f"Image test failed: {e}")
        return False


if __name__ == "__main__":
    print(f"=== VLM Integration Test (backend: {INFERENCE_BACKEND}, model: {MODEL}) ===\n")

    if not test_health():
        print(f"\nllama-server is not reachable at {BASE_URL}. Is it running?")
        exit(1)

    test_text_only()
    test_image_inference()

    print("\n=== Test complete ===")
