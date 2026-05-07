from pymavlink import mavutil


class EventMonitor:
    def __init__(self, connection, state_machine):
        self.connection = connection
        self.state_machine = state_machine
        self.last_mode = None
        self.last_alt = 0

    def check(self):
        msg = self.connection.recv_match(blocking=False)
        if msg is None:
            return

        msg_type = msg.get_type()

        if msg_type == "MISSION_ITEM_REACHED":
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
