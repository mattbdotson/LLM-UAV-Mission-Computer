from pymavlink import mavutil

class Executor:
    def __init__(self, connection):
        self.connection = connection
        print("Executor initialized")

    def execute(self, command):
        cmd = command.get("command")
        params = command.get("params", {})

        if cmd == "goto_waypoint":
            self._goto_waypoint(
                params["lat"],
                params["lon"],
                params["alt"]
            )
        elif cmd == "rtl":
            self._rtl()
        else:
            print(f"Unknown command: {cmd}")

    def _goto_waypoint(self, lat, lon, alt):
        print(f"Executing goto_waypoint: lat={lat}, lon={lon}, alt={alt}")
        self.connection.mav.mission_item_int_send(
            0, 0, 0,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            2, 1, 0, 0, 0, 0,
            int(lat * 1e7),
            int(lon * 1e7),
            alt
        )

    def _rtl(self):
        print("Executing RTL")
        self.connection.mav.command_long_send(
            0, 0,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0, 0, 0, 0, 0, 0, 0, 0
        )
