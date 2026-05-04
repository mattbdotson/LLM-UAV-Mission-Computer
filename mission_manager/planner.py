import json
import requests
import os
from dotenv import load_dotenv
from map_compositor import MapCompositor
from map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET

load_dotenv()

VILA_HOST = os.getenv('VILA_HOST', 'localhost')
VILA_PORT = os.getenv('VILA_PORT', '5000')
VILA_URL = f"http://{VILA_HOST}:{VILA_PORT}/generate"

SYSTEM_PROMPT = """You are an autonomous mission planning AI for a fixed-wing UAV.
You are given a top-down map image of the current flight area and the aircraft's current state.

On the map:
- Blue arrow = aircraft current position and heading direction
- Red crosshair = mission target
- Blue trail = recent flight path
- Compass rose = top left corner

Your current mission: Fly to the red crosshair target and orbit it.

You must respond with a single JSON object and nothing else. No explanation, no markdown.

Response format:
{
    "command": "goto_pixel",
    "reasoning": "explanation of what you see and why",
    "params": {
        "x": 200,
        "y": 200
    }
}

Where x and y are pixel coordinates (0-384) on the map image indicating where the aircraft should fly next.
Or use these commands instead if appropriate:
{
    "command": "loiter",
    "reasoning": "explanation",
    "params": {
        "x": 200,
        "y": 200,
        "radius": 500,
        "alt": 150
    }
}
{
    "command": "rtl",
    "reasoning": "explanation",
    "params": {}
}"""

class Planner:
    def __init__(self, stub=False):
        self.stub = stub
        self.compositor = MapCompositor(MAP_TILE_PATH, MAP_BOUNDS)
        print(f"Planner initialized ({'stub' if stub else 'VLM'} mode)")

    def decide(self, state):
        if self.stub:
            return self._stub_response(state)
        else:
            return self._vlm_response(state)

    def _vlm_response(self, state):
        image_b64 = self.compositor.compose(state, MISSION_TARGET)

        if image_b64 is None:
            print("Map composition failed — falling back to RTL")
            return {"command": "rtl", "reasoning": "Map error", "params": {}}

        prompt = f"Current aircraft state: alt={state.get('alt', 0):.0f}m, heading={state.get('heading', 0):.0f}°, airspeed={state.get('airspeed', 0):.0f}m/s\n\nWhat should the aircraft do next?"

        try:
            response = requests.post(VILA_URL, json={
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "image": image_b64,
                "stream": False
            }, timeout=60)

            raw = response.json()["response"]
            print(f"VLM raw response: {raw}")
            command = json.loads(raw)
            print(f"Planner decision: {json.dumps(command, indent=2)}")
            return command

        except Exception as e:
            print(f"VLM error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "VLM error", "params": {}}

    def _stub_response(self, state):
        response = {
            "command": "goto_pixel",
            "reasoning": "Stub mode - flying toward mission target pixel",
            "params": {
                "x": 193,
                "y": 192
            }
        }
        print(f"Planner decision: {json.dumps(response, indent=2)}")
        return response