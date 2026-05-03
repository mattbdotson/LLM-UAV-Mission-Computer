import time
from telemetry import TelemetryListener
from planner import Planner
from executor import Executor

CONNECTION_STRING = "udp:localhost:14552"
PLANNING_INTERVAL = 10  # seconds between planning cycles

def main():
    print("Starting mission manager...")

    telemetry = TelemetryListener(CONNECTION_STRING)
    planner = Planner(stub=False)
    executor = Executor(telemetry.connection)
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

