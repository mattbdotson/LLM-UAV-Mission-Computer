# Block Definition Document

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: SITL simulation phase only
- Last updated: 2026-05-07

## System Context

The LLM-UAV Mission Computer sits between the autopilot and the VLM inference engine. It translates autopilot telemetry into visual context for the VLM, and translates VLM decisions into MAVLink commands for the autopilot.

```
┌─────────────────────────────────────────────────────┐
│              LLM-UAV Mission Computer               │
│                                                     │
│  TelemetryListener → EventMonitor → StateMachine    │
│                                          ↓          │
│                       Planner → MapCompositor       │
│                          ↓                          │
│                       Backend → [VLM]               │
│                          ↓                          │
│                       Executor                      │
└─────────────────────────────────────────────────────┘
        ↕ MAVLink                      ↕ HTTP
   [Autopilot]                  [Inference Server]
```

## Block Definitions

### BLK-001: TelemetryListener
**Responsibility:** Owns the MAVLink connection. Drains all messages each tick. Maintains current aircraft state.
**Inputs:** MAVLink UDP stream from autopilot
**Outputs:** Aircraft state dict (lat, lon, alt, heading, airspeed, mode, armed), raw message buffer
**Key attributes:** Single owner of MAVLink connection — no other block reads from the connection directly

### BLK-002: EventMonitor
**Responsibility:** Detects meaningful events from the MAVLink message stream and fires them to the StateMachine.
**Inputs:** Raw message buffer from TelemetryListener
**Outputs:** Events (waypoint_reached, altitude_reached, mode_changed, no_progress)
**Key attributes:** Does not own MAVLink connection. Tracks time since last waypoint for no_progress detection.

### BLK-003: StateMachine
**Responsibility:** FSM engine. Maintains mission state. Calls Planner at decision points. Calls Executor with decisions.
**Inputs:** Events from EventMonitor
**Outputs:** Commands to Executor, context updates to MissionContext
**Key attributes:** Only block that calls Planner. Owns state transitions.

### BLK-004: MissionContext
**Responsibility:** Accumulates mission memory across the flight. Provides decision history to Planner.
**Inputs:** Decision records from StateMachine
**Outputs:** decisions_summary(), waypoints_summary() for prompt population
**Key attributes:** Persistent across the mission. Provides LLM episodic memory.

### BLK-005: Planner
**Responsibility:** Generates map image, loads prompt template, calls inference backend, parses response.
**Inputs:** Aircraft state, MissionContext, event type
**Outputs:** Command dict (command, reasoning, params)
**Key attributes:** Owns MapCompositor. Loads prompt from file per event type. Falls back to RTL on any error.

### BLK-006: MapCompositor
**Responsibility:** Draws aircraft position, heading, trail, and mission markers onto base map tile. Encodes as base64 PNG.
**Inputs:** Aircraft state, mission target coordinates, map tile
**Outputs:** base64 PNG image string
**Key attributes:** Saves debug images per call. Stores last bounds for pixel_to_gps conversion.

### BLK-007: InferenceBackend (abstract)
**Responsibility:** Sends prompt and image to VLM inference server. Returns raw text response.
**Inputs:** System prompt, user prompt, base64 image
**Outputs:** Raw text response string
**Key attributes:** Pluggable — concrete implementations for llama.cpp, Ollama, TensorRT. Selected via INFERENCE_BACKEND env var.

### BLK-008: Executor
**Responsibility:** Translates command dicts into MAVLink commands. Handles pixel-to-GPS conversion.
**Inputs:** Command dict from StateMachine
**Outputs:** MAVLink commands to autopilot
**Key attributes:** Owns pixel_to_gps conversion via MapCompositor reference. Clamps pixel coordinates to valid range.
