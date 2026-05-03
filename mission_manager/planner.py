import json
import requests
import os

OLLAMA_URL = f"http://{os.getenv('OLLAMA_HOST', 'localhost')}:11434/api/generate"
MODEL = "llama3.2:1b"

SYSTEM_PROMPT = """You are an autonomous mission planning AI for a fixed-wing UAV.
You receive the current aircraft state and must decide what the aircraft should do next.
You must respond with a single JSON object and nothing else. No explanation, no markdown.

Available commands:
- goto_waypoint: fly to a specific location
- loiter: circle a point at current altitude  
- rtl: return to launch
- search_pattern: fly a search pattern over an area

Response format:
{
    "command": "goto_waypoint",
    "reasoning": "explanation of decision",
    "params": {
        "lat": 0.0,
        "lon": 0.0,
        "alt": 100
    }
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
            })
            
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