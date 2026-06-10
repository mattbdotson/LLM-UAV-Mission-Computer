from enum import Enum


class MissionState(Enum):
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    TRANSIT = "TRANSIT"
    ON_TASK = "ON_TASK"
    STUCK = "STUCK"
    RETURNING = "RETURNING"
    LANDED = "LANDED"


# mbase:implements BHV-mission-fsm
class StateMachine:
    def __init__(self, mission_context, planner, executor, telemetry):
        self.state = MissionState.PREFLIGHT
        self.context = mission_context
        self.planner = planner
        self.executor = executor
        self.telemetry = telemetry

    def transition_to(self, new_state):
        print(f"[StateMachine] {self.state.value} → {new_state.value}")
        self.state = new_state
        self.context.current_state = new_state.value

    def on_event(self, event, data=None):
        print(f"[StateMachine] Event: {event} in state {self.state.value}")
        handler = getattr(self, f"handle_{event}", self.handle_unknown)
        handler(data or {})

    def handle_unknown(self, data):
        pass

    def handle_altitude_reached(self, data):
        if self.state == MissionState.TAKEOFF:
            self.transition_to(MissionState.TRANSIT)
            print("[StateMachine] Cruise altitude reached, consulting LLM for first waypoint...")
            current_state = self.telemetry.get_state()
            self._llm_decision("transit_started", 0, current_state)

    def handle_mode_changed(self, data):
        if self.state == MissionState.RETURNING:
            if data.get("mode") == 9:  # LAND mode
                self.transition_to(MissionState.LANDED)

    def handle_waypoint_reached(self, data):
        seq = data.get("seq", 0)
        current_state = self.telemetry.get_state()

        if self.state == MissionState.TRANSIT:
            self.transition_to(MissionState.ON_TASK)

        if self.state == MissionState.ON_TASK:
            if current_state.get('pixel_y', 999) < 20:
                print("[StateMachine] Aircraft at northern map boundary — auto RTL")
                self.executor.execute({"command": "rtl", "reasoning": "Reached northern map boundary", "params": {}})
                self.transition_to(MissionState.RETURNING)
                return
            self._llm_decision("waypoint_reached", seq, current_state)
        elif self.state == MissionState.STUCK:
            self.transition_to(MissionState.ON_TASK)
            self._llm_decision("waypoint_reached", seq, current_state)

    def handle_no_progress(self, data):
        if self.state == MissionState.ON_TASK:
            elapsed = data.get("elapsed", 0)
            print(f"[StateMachine] No progress for {elapsed:.0f}s — transitioning to STUCK")
            self.transition_to(MissionState.STUCK)
            self.context.record_stuck()
            current_state = self.telemetry.get_state()
            self._llm_decision("stuck", 0, current_state)

    def _llm_decision(self, trigger, seq, telemetry_state):
        print(f"[StateMachine] Consulting LLM for {trigger} at waypoint {seq}")
        print(f"[StateMachine] Passing telemetry state to planner: {telemetry_state}")
        print(f"[LLM] *** Invoking Gemma 4 E2B for event: {trigger} at waypoint {seq} ***")

        command = self.planner.decide_with_context(
            state=telemetry_state,
            context=self.context,
            event=trigger,
            event_data={"seq": seq}
        )

        print(f"[LLM] *** Decision: {command.get('command')} — {command.get('reasoning', '')} ***")

        self.context.add_decision(
            trigger=trigger,
            state=self.state.value,
            command=command.get("command"),
            reasoning=command.get("reasoning", ""),
            params=command.get("params", {}),
            progress=command.get("progress"),
            next_intent=command.get("next_intent"),
        )

        self.context.add_waypoint_visit(
            seq=seq,
            lat=telemetry_state.get('lat', 0),
            lon=telemetry_state.get('lon', 0),
            decision=command.get('command'),
            reasoning=command.get('reasoning', '')
        )

        cmd = command.get("command")
        if cmd == "rtl":
            self.transition_to(MissionState.RETURNING)

        self.executor.execute(command)
