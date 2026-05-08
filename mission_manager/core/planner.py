import json
import os
import time
import base64
import datetime
import shutil
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
        self.run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_dir = os.path.join(os.path.dirname(__file__), '..', 'debug', 'maps', self.run_id)
        os.makedirs(self.debug_dir, exist_ok=True)
        print(f"[Planner] Debug images will be saved to: {self.debug_dir}")
        self.mission_dir = os.path.join(os.path.dirname(__file__), '..', 'missions', self.run_id)
        os.makedirs(self.mission_dir, exist_ok=True)
        print(f"[Planner] Mission archive: {self.mission_dir}")
        prompts_src = os.path.join(os.path.dirname(__file__), '..', 'prompts')
        shutil.copytree(prompts_src, os.path.join(self.mission_dir, 'prompts'))
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

        self._save_debug_map(image_b64, "decide", seq=0)

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

        self._save_debug_map(image_b64, event, seq=event_data.get("seq", 0) if event_data else 0)

        # Compute pixel position from GPS and inject into state for prompt templates
        state = dict(state)  # don't mutate caller's dict
        lat, lon = state.get("lat"), state.get("lon")
        if lat is not None and lon is not None:
            full_x, full_y = self.compositor.gps_to_pixel(lat, lon)
            vlm_w, vlm_h = self.compositor.vlm_size
            state["pixel_x"] = int(full_x * vlm_w / self.compositor.w)
            state["pixel_y"] = int(full_y * vlm_h / self.compositor.h)
            print(f"[Planner] Aircraft pixel position: ({state['pixel_x']}, {state['pixel_y']})")

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

    def set_mission_info(self, objective):
        info_path = os.path.join(self.mission_dir, 'mission_info.txt')
        with open(info_path, 'w') as f:
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Run ID: {self.run_id}\n")
            f.write(f"Model: {self.backend.get_name()}\n")
            f.write(f"Objective: {objective}\n")
        print(f"[Planner] Mission info saved: {info_path}")

    def _save_debug_map(self, image_b64, event, seq=0):
        filename = os.path.join(self.debug_dir, f"{event}_seq{seq}_{int(time.time())}.png")
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

        formatted_prompt = template.format(
            objective=context.objective,
            state=context.current_state,
            event=event,
            waypoints_summary=context.waypoints_summary(),
            decisions_summary=context.decisions_summary(),
            alt=f"{state.get('alt', 0):.0f}",
            heading=f"{state.get('heading', 0):.0f}",
            airspeed=f"{state.get('airspeed', 0):.0f}",
            seq=event_data.get("seq", 0) if event_data else 0,
            total_waypoints=context.total_waypoints,
            pixel_x=state.get('pixel_x', 0),
            pixel_y=state.get('pixel_y', 0),
        )
        prompt_filename = os.path.join(self.mission_dir, f"{event}_{int(time.time())}_user_prompt.txt")
        with open(prompt_filename, 'w') as f:
            f.write(formatted_prompt)
        return formatted_prompt