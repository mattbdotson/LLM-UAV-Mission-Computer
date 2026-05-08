from dataclasses import dataclass, field
from typing import List, Dict
import time


@dataclass
class WaypointVisit:
    seq: int
    timestamp: float
    lat: float
    lon: float
    decision: str
    reasoning: str


@dataclass
class MissionContext:
    objective: str
    total_waypoints: int = 0
    waypoints_visited: List[WaypointVisit] = field(default_factory=list)
    decisions: List[Dict] = field(default_factory=list)
    current_state: str = "PREFLIGHT"
    stuck_count: int = 0
    start_time: float = field(default_factory=time.time)

    def record_stuck(self):
        self.stuck_count += 1

    def add_waypoint_visit(self, seq, lat, lon, decision, reasoning):
        self.waypoints_visited.append(WaypointVisit(
            seq=seq,
            timestamp=time.time(),
            lat=lat,
            lon=lon,
            decision=decision,
            reasoning=reasoning
        ))

    def add_decision(self, trigger, state, command, reasoning, params=None):
        self.decisions.append({
            "trigger": trigger,
            "state": state,
            "command": command,
            "reasoning": reasoning,
            "params": params or {},
            "timestamp": time.time()
        })

    def decisions_summary(self):
        if not self.decisions:
            return "No decisions made yet"
        lines = []
        for d in self.decisions[-2:]:
            lines.append(f"- [{d['state']}] {d['trigger']}: {d['command']} — {d['reasoning']}")
        return "\n".join(lines[-2:])

    def waypoints_summary(self):
        return f"{len(self.waypoints_visited)} of {self.total_waypoints} visited"
