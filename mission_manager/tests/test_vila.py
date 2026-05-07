import requests
import base64
import json
import os
from map_compositor import MapCompositor
from map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET
from dotenv import load_dotenv

load_dotenv()

VILA_HOST = os.getenv('VILA_HOST', 'localhost')
VILA_PORT = os.getenv('VILA_PORT', '5000')
VILA_URL = f"http://{VILA_HOST}:{VILA_PORT}"

def test_health():
    print("Testing VILA health endpoint...")
    try:
        r = requests.get(f"{VILA_URL}/health", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_text_only():
    print("\nTesting text-only inference...")
    try:
        r = requests.post(f"{VILA_URL}/generate", json={
            "prompt": "What is a waypoint in aviation? Answer in one sentence.",
            "system": "You are a helpful assistant.",
            "stream": False
        }, timeout=60)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()['response']}")
        return True
    except Exception as e:
        print(f"Text test failed: {e}")
        return False

def test_image_inference():
    print("\nTesting image + text inference...")
    
    compositor = MapCompositor(MAP_TILE_PATH, MAP_BOUNDS)
    state = {
        "lat": -35.363,
        "lon": 149.165,
        "heading": 45,
        "alt": 150,
        "airspeed": 22
    }
    image_b64 = compositor.compose(state, MISSION_TARGET)
    
    system_prompt = open("prompts/system_prompt.txt").read()
    user_prompt = "Current aircraft state: alt=150m, heading=45°, airspeed=22m/s\n\nWhat should the aircraft do next?"
    
    try:
        r = requests.post(f"{VILA_URL}/generate", json={
            "prompt": user_prompt,
            "system": system_prompt,
            "image": image_b64,
            "stream": False
        }, timeout=120)
        
        print(f"Status: {r.status_code}")
        raw = r.json()["response"]
        print(f"Raw response: {raw}")
        
        try:
            command = json.loads(raw)
            print(f"Parsed command: {json.dumps(command, indent=2)}")
        except json.JSONDecodeError:
            print("Response was not valid JSON")
            
        return True
    except Exception as e:
        print(f"Image test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== VILA Integration Test ===\n")
    
    if not test_health():
        print("\nVILA server is not reachable. Is it running?")
        exit(1)
    
    test_text_only()
    test_image_inference()
    
    print("\n=== Test complete ===")