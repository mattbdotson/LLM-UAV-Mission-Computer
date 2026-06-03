from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
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
    start_pixel_x: Optional[int] = None
    start_pixel_y: Optional[int] = None
    last_progress: Optional[str] = None
    last_next_intent: Optional[str] = None
    decisions_log_path: Optional[str] = None

    def record_stuck(self):
        self.stuck_count += 1

    def set_start_pixel(self, x, y):
        if self.start_pixel_x is None and self.start_pixel_y is None:
            self.start_pixel_x = x
            self.start_pixel_y = y

    def add_waypoint_visit(self, seq, lat, lon, decision, reasoning):
        self.waypoints_visited.append(WaypointVisit(
            seq=seq,
            timestamp=time.time(),
            lat=lat,
            lon=lon,
            decision=decision,
            reasoning=reasoning
        ))

    def add_decision(self, trigger, state, command, reasoning, params=None, progress=None, next_intent=None):
        entry = {
            "trigger": trigger,
            "state": state,
            "command": command,
            "reasoning": reasoning,
            "params": params or {},
            "timestamp": time.time(),
            "progress": progress,
            "next_intent": next_intent,
        }
        self.decisions.append(entry)
        if self.decisions_log_path:
            with open(self.decisions_log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

    def decisions_summary(self):
        if not self.decisions:
            return "No decisions made yet"
        lines = []
        for d in self.decisions[-2:]:
            lines.append(f"- [{d['state']}] {d['trigger']}: {d['command']} — {d['reasoning']}")
        return "\n".join(lines[-2:])

    def waypoints_summary(self):
        return f"{len(self.waypoints_visited)} of {self.total_waypoints} visited"
