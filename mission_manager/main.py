import time
import os
import subprocess
import sys
import requests as req
from dotenv import load_dotenv
from core.telemetry import TelemetryListener
from core.planner import Planner
from core.executor import Executor
from core.mission_context import MissionContext
from core.state_machine import StateMachine, MissionState
from core.event_monitor import EventMonitor

load_dotenv(os.path.join(os.path.dirname(__file__), 'config', '.env'))

CONNECTION_STRING = "udp:localhost:14552"
MISSION_OBJECTIVE = "Fly a complete box pattern, then RTL. Choose your own corner coordinates to form a reasonable box shape on the map. Remember which corners you have visited and complete all four corners before RTL."
TOTAL_WAYPOINTS = 5

def prevent_sleep():
    if sys.platform.startswith('linux'):
        try:
            subprocess.Popen(['systemd-inhibit', '--what=sleep', '--who=LLM-UAV',
                            '--why=Mission in progress', '--mode=block',
                            'sleep', 'infinity'])
            print("Sleep inhibited for mission duration")
        except Exception as e:
            print(f"Could not inhibit sleep: {e}")


def cleanup_stale_sitl():
    print("Cleaning up any stale SITL processes...")
    for pattern in ("arduplane", "sim_vehicle", "mavproxy", "xterm.*ArduPlane"):
        subprocess.run(["pkill", "-9", "-f", pattern], check=False)
    time.sleep(2)


def start_sitl():
    cleanup_stale_sitl()
    print("Starting SITL...")
    sitl_process = subprocess.Popen(
        [
            "sim_vehicle.py",
            "-v", "ArduPlane",
            "-f", "plane",
            "--console",
            "--map",
            "--out", "udp:localhost:14552"
        ],
        cwd=os.path.expanduser("~/ardupilot/ArduPlane")
    )
    print("Waiting for SITL to initialize...")
    time.sleep(30)
    print("SITL ready.")
    return sitl_process

def wait_for_vila(host, port, timeout=120):
    url = f"http://{host}:{port}/health"
    print(f"Waiting for VILA server at {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = req.get(url, timeout=3)
            if r.status_code == 200:
                print("VILA server is ready")
                return True
        except:
            pass
        time.sleep(3)
    print("VILA server timeout — proceeding anyway")
    return False

def main():
    prevent_sleep()
    print("Starting mission manager...")

    sitl_process = start_sitl()

    telemetry = TelemetryListener(CONNECTION_STRING)
    planner = Planner(stub=False)
    if hasattr(planner.backend, 'clear_cache'):
        planner.backend.clear_cache()
    executor = Executor(telemetry.connection)

    backend = os.getenv('INFERENCE_BACKEND', 'vila').lower()
    if backend == 'vila':
        vila_host = os.getenv('VILA_HOST', 'localhost')
        vila_port = os.getenv('VILA_PORT', '5000')
        wait_for_vila(vila_host, vila_port)

    mission_context = MissionContext(
        objective=MISSION_OBJECTIVE,
        total_waypoints=TOTAL_WAYPOINTS,
    )
    planner.set_mission_info(mission_context.objective)

    state_machine = StateMachine(mission_context, planner, executor, telemetry)
    event_monitor = EventMonitor(telemetry, state_machine)

    executor.arm_and_takeoff(altitude=100)
    state_machine.transition_to(MissionState.TAKEOFF)

    print("Mission manager running. Press Ctrl+C to stop.")

    while True:
        telemetry.update()
        event_monitor.check(telemetry.get_raw_messages())
        time.sleep(0.1)


if __name__ == "__main__":
    main()
