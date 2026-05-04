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

def load_prompt(filename):
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', filename)
    with open(prompt_path, 'r') as f:
        return f.read()

class Planner:
    def __init__(self, stub=False):
        self.stub = stub
        self.compositor = MapCompositor(MAP_TILE_PATH, MAP_BOUNDS)
        self.system_prompt = load_prompt('system_prompt.txt')
        self.user_prompt_template = load_prompt('user_prompt.txt')
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

        prompt = self.user_prompt_template.format(
            alt=f"{state.get('alt', 0):.0f}",
            heading=f"{state.get('heading', 0):.0f}",
            airspeed=f"{state.get('airspeed', 0):.0f}"
        )

        try:
            response = requests.post(VILA_URL, json={
                "prompt": prompt,
                "system": self.system_prompt,
                "image": image_b64,
                "stream": False
            }, timeout=60)

            raw = response.json()["response"]
            print(f"VLM raw response: {raw}")
            command = json.loads(raw)
            print(f"Planner decision: {json.dumps(command, indent=2)}")
            return command

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "Parse error", "params": {}}
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