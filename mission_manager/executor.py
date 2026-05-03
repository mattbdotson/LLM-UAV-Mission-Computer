from pymavlink import mavutil
import time

class Executor:
    def __init__(self, connection):
        self.connection = connection
        print("Executor initialized")

    def arm_and_takeoff(self, altitude=100):
     print("Setting mode to GUIDED...")
     self.connection.mav.command_long_send(
        0, 0,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0, 1,
        mavutil.mavlink.PLANE_MODE_GUIDED,
        0, 0, 0, 0, 0
     )
     time.sleep(2)

     print("Arming throttle...")
     self.connection.mav.command_long_send(
        0, 0,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 21196, 0, 0, 0, 0, 0
     )
     time.sleep(2)

     print("Switching to TAKEOFF mode...")
     self.connection.mav.command_long_send(
        0, 0,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0, 1,
        mavutil.mavlink.PLANE_MODE_TAKEOFF,
        0, 0, 0, 0, 0
     )
     time.sleep(10)
     print("Takeoff sequence complete")
     print("Switching back to GUIDED mode...")
     self.connection.mav.command_long_send(
      0, 0,
     mavutil.mavlink.MAV_CMD_DO_SET_MODE,
     0, 1,
     mavutil.mavlink.PLANE_MODE_GUIDED,
     0, 0, 0, 0, 0
     )
     time.sleep(2)
     print("Ready for waypoint commands")


    def execute(self, command):
        cmd = command.get("command")
        params = command.get("params", {})

        if cmd == "goto_waypoint":
            self._goto_waypoint(
                params["lat"],
                params["lon"],
                params.get("alt", 100)
            )
        elif cmd == "loiter":
            self._loiter(
                params["lat"],
                params["lon"],
                params.get("alt", 100),
                params.get("radius", 500)
            )
        elif cmd == "rtl":
            self._rtl()
        else:
            print(f"Unknown command: {cmd}")

    def _goto_waypoint(self, lat, lon, alt=100):
         lat, lon, alt = float(lat), float(lon), float(alt)
         alt = max(alt, 50)  # never fly below 50m
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

    def _loiter(self, lat, lon, alt, radius=1000):
     lat, lon, alt, radius = float(lat), float(lon), float(alt), float(radius)
     print(f"Executing loiter: lat={lat}, lon={lon}, alt={alt}, radius={radius}")
     self.connection.mav.command_long_send(
        0, 0,
        mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
        0,
        0, 0, radius, 0,
        lat, lon, alt
    )