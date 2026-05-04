from pymavlink import mavutil
import time

class Executor:
    def __init__(self, connection):
        self.connection = connection
        self._compositor = None
        print("Executor initialized")

    def _get_compositor(self):
        if self._compositor is None:
            from map_compositor import MapCompositor
            from map_config import MAP_TILE_PATH, MAP_BOUNDS
            self._compositor = MapCompositor(MAP_TILE_PATH, MAP_BOUNDS)
        return self._compositor

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
                float(params.get("alt", 100))
            )
        elif cmd == "goto_pixel":
            x = int(params.get("x", 192))
            y = int(params.get("y", 192))
            alt = float(params.get("alt", 100))
            lat, lon = self._get_compositor().pixel_to_gps(x, y)
            print(f"Pixel ({x},{y}) → GPS lat={lat:.5f}, lon={lon:.5f}")
            self._goto_waypoint(lat, lon, alt)
        elif cmd == "loiter":
            x = params.get("x")
            y = params.get("y")
            if x is not None and y is not None:
                lat, lon = self._get_compositor().pixel_to_gps(int(x), int(y))
            else:
                lat = float(params.get("lat", 0))
                lon = float(params.get("lon", 0))
            self._loiter(
                lat, lon,
                float(params.get("alt", 100)),
                float(params.get("radius", 500))
            )
        elif cmd == "fly_waypoints":
            self._fly_waypoints(params["waypoints"])
        elif cmd == "rtl":
            self._rtl()
        else:
            print(f"Unknown command: {cmd}")

    def _goto_waypoint(self, lat, lon, alt=100):
        lat, lon, alt = float(lat), float(lon), float(alt)
        alt = max(alt, 50)
        self.connection.mav.command_long_send(
            0, 0,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 1,
            mavutil.mavlink.PLANE_MODE_GUIDED,
            0, 0, 0, 0, 0
        )
        time.sleep(1)
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

    def _loiter(self, lat, lon, alt=100, radius=500):
        print(f"Executing loiter: lat={lat}, lon={lon}, alt={alt}, radius={radius}")
        self.connection.mav.command_long_send(
            0, 0,
            mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
            0,
            0, 0, radius, 0,
            lat, lon, alt
        )

    def _fly_waypoints(self, waypoints):
        print(f"Executing fly_waypoints: {len(waypoints)} waypoints")
        for i, wp in enumerate(waypoints):
            self.connection.mav.mission_item_int_send(
                0, 0, i,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                2, 1, 0, 0, 0, 0,
                int(wp["lat"] * 1e7),
                int(wp["lon"] * 1e7),
                wp["alt"]
            )

    def _rtl(self):
        print("Executing RTL")
        self.connection.mav.command_long_send(
            0, 0,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0, 0, 0, 0, 0, 0, 0, 0
        )