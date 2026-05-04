import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = f"http://{os.getenv('OLLAMA_HOST', 'localhost')}:11434/api/generate"
MODEL = "llama3.2:3b-instruct-q2_K"

SYSTEM_PROMPT = """You are an autonomous mission planning AI for a fixed-wing UAV.
You receive the current aircraft state and must decide what the aircraft should do next.
You must respond with a single JSON object and nothing else. No explanation, no markdown.

Your current mission: Fly a circular orbit (radius 2km)around Latitude: -35.34196902, Longitude: 149.15816552. at an altitude of 150 meters. After three full orbits, return to launch.
You must use combinations of the commands below to accomplish your mission.


Available commands:
- goto_waypoint: fly to a specific location. When using this command, you must specify a latitude, longitude, and altitude. The aircraft will fly to that point.
- loiter: circle a point at current altitude. When using this command, you must specify a latitude, longitude, altitude, and radius. The aircraft will circle that point at the specified radius.
- rtl: return to launch. The aircraft will fly back to the takeoff point and land.


Use the response format below. DO NOT DEVIATE FROM THIS FORMAT. 
    For goto_waypoint:

    "command": "goto_waypoint",
    "reasoning": "explanation of decision",
    "params": {
        "lat": 0.0,
        "lon": 0.0,
        "alt": 100
    }

    For loiter:

    "command": "loiter",
    "reasoning": "explanation of decision",
    "params": {
        "lat": 0.0,
        "lon": 0.0,
        "alt": 100
        "radius": 1000
    }

    For rtl:
    "command": "rtl"
}"""

class Planner:
    def __init__(self, stub=False):
        self.stub = stub
        print(f"Planner initialized ({'stub' if stub else 'LLM'} mode)")

    def decide(self, state):
        if self.stub:
            return self._stub_response(state)
        else:
            return self._llm_response(state)

    def _llm_response(self, state):
        prompt = f"Current aircraft state: {json.dumps(state)}\nWhat should the aircraft do next?"
        
        try:
            response = requests.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False
            }, timeout=60)

            raw = response.json()["response"]
            print(f"LLM raw response: {raw}")
            command = json.loads(raw)
            print(f"Planner decision: {json.dumps(command, indent=2)}")
            return command
            
        except Exception as e:
            print(f"LLM error: {e} — falling back to RTL")
            return {"command": "rtl", "reasoning": "LLM error", "params": {}}

    def _stub_response(self, state):
        response = {
            "command": "goto_waypoint",
            "reasoning": "Stub mode - flying to test waypoint",
            "params": {
                "lat": 51.8779,
                "lon": -2.2918,
                "alt": 100
            }
        }
        print(f"Planner decision: {json.dumps(response, indent=2)}")
        return response