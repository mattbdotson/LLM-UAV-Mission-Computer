import time


class EventMonitor:
    def __init__(self, telemetry, state_machine):
        self.telemetry = telemetry
        self.state_machine = state_machine
        self.last_mode = None
        self.last_alt = 0
        self.last_waypoint_time = time.time()
        self.no_progress_timeout = 600  # seconds
        self.no_progress_fired = False

    def check(self, messages):
        for msg in messages:
            msg_type = msg.get_type()

            if msg_type == "MISSION_ITEM_REACHED":
                self.last_waypoint_time = time.time()
                self.no_progress_fired = False
                self.state_machine.on_event("waypoint_reached", {
                    "seq": msg.seq
                })

            elif msg_type == "HEARTBEAT":
                mode = msg.custom_mode
                if mode != self.last_mode:
                    self.state_machine.on_event("mode_changed", {
                        "mode": mode,
                        "previous_mode": self.last_mode
                    })
                    self.last_mode = mode

            elif msg_type == "GLOBAL_POSITION_INT":
                alt = msg.relative_alt / 1000
                if self.last_alt < 50 and alt >= 50:
                    self.state_machine.on_event("altitude_reached", {
                        "alt": alt
                    })
                self.last_alt = alt

        elapsed = time.time() - self.last_waypoint_time
        if elapsed > self.no_progress_timeout and not self.no_progress_fired:
            current_state = self.telemetry.get_state()
            if current_state.get('alt', 0) > 50:  # only fire if airborne
                print(f"[EventMonitor] No progress for {elapsed:.0f}s — firing no_progress event")
                self.state_machine.on_event("no_progress", {"elapsed": elapsed})
                self.no_progress_fired = True
