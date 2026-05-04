import time
import os
import subprocess
import requests as req
from telemetry import TelemetryListener
from planner import Planner
from executor import Executor

CONNECTION_STRING = "udp:localhost:14552"
PLANNING_INTERVAL = 10

def start_sitl():
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
    import time
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
    print("Starting mission manager...")

    sitl_process = start_sitl()

    telemetry = TelemetryListener(CONNECTION_STRING)
    planner = Planner(stub=False)
    executor = Executor(telemetry.connection)

    vila_host = os.getenv('VILA_HOST', 'localhost')
    vila_port = os.getenv('VILA_PORT', '5000')
    wait_for_vila(vila_host, vila_port)


    executor.arm_and_takeoff(altitude=100)

    print("Mission manager running. Press Ctrl+C to stop.")

    last_plan_time = 0

    while True:
        telemetry.update()

        current_time = time.time()
        if current_time - last_plan_time >= PLANNING_INTERVAL:
            state = telemetry.get_state()
            if state and "lat" in state and abs(state["lat"]) > 1 and state.get("alt", 0) > 50:
                print(f"\nCurrent state: {state}")
                command = planner.decide(state)
                executor.execute(command)
                last_plan_time = current_time

        time.sleep(0.1)



if __name__ == "__main__":
    main()

