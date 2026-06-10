from pymavlink import mavutil

# mbase:implements CMP-telemetry
class TelemetryListener:
    def __init__(self, connection_string):
        print(f"Connecting to autopilot at {connection_string}")
        self.connection = mavutil.mavlink_connection(connection_string)
        self.connection.wait_heartbeat()
        print("Heartbeat received — connected to autopilot")
        self.state = {}
        self._last_messages = []

    def update(self):
        """Drain all available MAVLink messages, update state, and buffer
        every raw message for downstream consumers (e.g. EventMonitor)."""
        self._last_messages = []
        while True:
            msg = self.connection.recv_match(blocking=False)
            if msg is None:
                break

            self._last_messages.append(msg)
            msg_type = msg.get_type()

            if msg_type == "GLOBAL_POSITION_INT":
                self.state["lat"] = msg.lat / 1e7
                self.state["lon"] = msg.lon / 1e7
                self.state["alt"] = msg.relative_alt / 1000
                self.state["heading"] = msg.hdg / 100

            elif msg_type == "VFR_HUD":
                self.state["airspeed"] = msg.airspeed
                self.state["groundspeed"] = msg.groundspeed

            elif msg_type == "HEARTBEAT":
                self.state["mode"] = msg.custom_mode
                self.state["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def get_state(self) -> dict:
        return self.state

    def get_raw_messages(self):
        """Return the list of raw MAVLink messages received in the most recent
        update() call. Subsequent updates clear and refill this buffer."""
        return self._last_messages
