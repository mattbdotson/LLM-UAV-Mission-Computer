import json
import os
import time
import base64
from dotenv import load_dotenv
from backends import load_backend
from mapping.map_compositor import MapCompositor
from config.map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET, VLM_IMAGE_SIZE

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

def load_prompt(filename):
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', filename)
    with open(prompt_path, 'r') as f:
        return f.read()

class Planner:
    def __init__(self, stub=False):
        self.stub = stub
        self.backend = load_backend()
        self.compositor = MapCompositor(
            os.path.join(os.path.dirname(__file__), '..', 'assets', MAP_TILE_PATH),
            MAP_BOUNDS,
            vlm_size=VLM_IMAGE_SIZE
        )
        self.system_prompt = load_prompt('system_prompt.txt')
        self.user_prompt_template = load_prompt('user_prompt.txt')
        print(f"Planner initialized ({'stub' if stub else self.backend.get_name()} mode)")

    def decide(self, state):
        if self.stub:
            return self._stub_response(state)
        else:
            return self._inference_response(state)

    def _inference_response(self, state):
        image_b64 = self.compositor.compose(state, MISSION_TARGET)

        if image_b64 is None:
            print("Map composition failed — falling back to RTL")
            return {"command": "rtl", "reasoning": "Map error", "params": {}}

        self._save_debug_map(image_b64, "decide")

        prompt = self.user_prompt_template.format(
            alt=f"{state.get('alt', 0):.0f}",
            heading=f"{state.get('heading', 0):.0f}",
            airspeed=f"{state.get('airspeed', 0):.0f}"
        )

        try:
            raw = self.backend.generate(
                system_prompt=self.system_prompt,
                user_prompt=prompt,
                image_b64=image_b64
            )
            print(f"[{self.backend.get_name()}] raw response: {raw}")
            command = json.loads(raw)
            print(f"Planner decision: {json.dumps(command, indent=2)}")
            return command

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "Parse error", "params": {}}
        except Exception as e:
            print(f"Backend error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "Backend error", "params": {}}

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

    def decide_with_context(self, state, context, event, event_data=None):
        if self.stub:
            return self._stub_response(state)

        print(f"[Planner] Composing map image for event: {event}")
        image_b64 = self.compositor.compose(state, MISSION_TARGET)
        if image_b64 is None:
            return {"command": "rtl", "reasoning": "Map error", "params": {}}
        print(f"[Planner] Map image composed, size: {len(image_b64)} bytes")

        self._save_debug_map(image_b64, event)

        user_prompt = self._load_event_prompt(event, state, context, event_data)

        try:
            print(f"[Planner] Sending to backend — system prompt length: {len(self.system_prompt)}")
            print(f"[Planner] Sending to backend — user prompt length: {len(user_prompt)}")
            print(f"[Planner] Sending to backend — image included: {image_b64 is not None and len(image_b64) > 0}")
            raw = self.backend.generate(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                image_b64=image_b64
            )
            print(f"[{self.backend.get_name()}] raw response: {raw}")
            command = json.loads(raw)
            print(f"Planner decision: {json.dumps(command, indent=2)}")
            return command
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "Parse error", "params": {}}
        except Exception as e:
            print(f"Backend error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "Backend error", "params": {}}

    def _save_debug_map(self, image_b64, event):
        os.makedirs("debug/maps", exist_ok=True)
        filename = f"debug/maps/{event}_{int(time.time())}.png"
        with open(filename, 'wb') as f:
            f.write(base64.b64decode(image_b64))
        print(f"[Planner] Debug map saved: {filename}")

    def _load_event_prompt(self, event, state, context, event_data):
        template_path = os.path.join(
            os.path.dirname(__file__), '..', 'prompts', f'{event}.txt'
        )
        try:
            with open(template_path, 'r') as f:
                template = f.read()
        except FileNotFoundError:
            template = "Current state: {state}\nEvent: {event}\nWhat should the aircraft do next?"

        return template.format(
            objective=context.objective,
            state=context.current_state,
            event=event,
            waypoints_summary=context.waypoints_summary(),
            decisions_summary=context.decisions_summary(),
            alt=f"{state.get('alt', 0):.0f}",
            heading=f"{state.get('heading', 0):.0f}",
            airspeed=f"{state.get('airspeed', 0):.0f}",
            seq=event_data.get("seq", 0) if event_data else 0,
            total_waypoints=context.total_waypoints
        )