from pymavlink import mavutil

class TelemetryListener:
    def __init__(self, connection_string):
        print(f"Connecting to autopilot at {connection_string}")
        self.connection = mavutil.mavlink_connection(connection_string)
        self.connection.wait_heartbeat()
        print("Heartbeat received — connected to autopilot")
        self.state = {}

    def update(self):
        msg = self.connection.recv_match(blocking=False)
        if msg is None:
            return
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

    def get_state(self):
        return self.state
