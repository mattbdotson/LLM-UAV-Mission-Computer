import json

class Planner:
    def __init__(self, stub=True):
        self.stub = stub
        print(f"Planner initialized ({'stub' if stub else 'LLM'} mode)")

    def decide(self, state):
        if self.stub:
            return self._stub_response(state)
        else:
            # LLM inference will go here later
            pass

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
