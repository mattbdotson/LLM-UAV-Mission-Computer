import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from mapping.map_compositor import MapCompositor
from config.map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET, VLM_IMAGE_SIZE
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
OLLAMA_PORT = os.getenv('OLLAMA_PORT', '11434')
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

MISSION_MANAGER_DIR = os.path.join(os.path.dirname(__file__), '..')

def test_health():
    print("Testing Ollama health endpoint...")
    try:
        r = requests.get(f"{OLLAMA_URL}/api/version", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_text_only():
    print("\nTesting moondream text-only inference...")
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": "moondream",
            "messages": [{"role": "user", "content": "What is a waypoint in aviation? Answer in one sentence."}],
            "stream": False
        }, timeout=60)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()['message']['content']}")
        return True
    except Exception as e:
        print(f"Text test failed: {e}")
        return False

def test_image_inference():
    print("\nTesting moondream image + text inference...")

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

    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": "moondream",
            "messages": [{"role": "user", "content": "Describe this image.", "images": [image_b64]}],
            "stream": False
        }, timeout=120)

        print(f"Status: {r.status_code}")
        print(f"Full response: {r.json()}")

        return True
    except Exception as e:
        print(f"Image test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Moondream Integration Test ===\n")

    if not test_health():
        print("\nOllama is not reachable. Is it running?")
        exit(1)

    test_text_only()
    test_image_inference()

    print("\n=== Test complete ===")
