# Interface Control Document

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: SITL simulation phase only
- Last updated: 2026-05-07

## Interface Definitions

### ICD-001: TelemetryListener → EventMonitor
**Type:** In-process Python list
**Data:** List of raw pymavlink message objects from current tick
**Method:** telemetry.get_raw_messages()
**Frequency:** Every 100ms (main loop tick)

### ICD-002: TelemetryListener → StateMachine (via Planner)
**Type:** In-process Python dict
**Data:**
```python
{
    "lat": float,      # degrees
    "lon": float,      # degrees
    "alt": float,      # meters AGL
    "heading": float,  # degrees 0-360
    "airspeed": float, # m/s
    "groundspeed": float, # m/s
    "mode": int,       # ArduPilot mode number
    "armed": bool,
    "pixel_x": int,    # current position on VLM image
    "pixel_y": int
}
```

### ICD-003: Planner → InferenceBackend
**Type:** HTTP POST
**Endpoint:** /v1/chat/completions (OpenAI-compatible)
**Request:**
```json
{
    "model": "gemma4-e2b",
    "messages": [
        {"role": "system", "content": "<system_prompt>"},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            {"type": "text", "text": "<user_prompt>"}
        ]}
    ],
    "max_tokens": 512,
    "cache_prompt": false,
    "chat_template_kwargs": {"enable_thinking": false}
}
```
**Response:** OpenAI chat completion object

### ICD-004: StateMachine → Executor
**Type:** In-process Python dict
**Data (command schema):**
```json
{"command": "goto_pixel", "reasoning": "string", "params": {"x": int, "y": int}}
{"command": "loiter", "reasoning": "string", "params": {"x": int, "y": int, "radius": float, "alt": float}}
{"command": "rtl", "reasoning": "string", "params": {}}
```

### ICD-005: Executor → Autopilot
**Type:** MAVLink UDP
**Port:** 14552
**Messages used:**
- MAV_CMD_DO_SET_MODE — switch flight mode
- MAV_CMD_COMPONENT_ARM_DISARM — arm/disarm
- MAV_CMD_NAV_WAYPOINT via mission_item_int_send — goto waypoint
- MAV_CMD_NAV_LOITER_UNLIM — loiter
- MAV_CMD_NAV_RETURN_TO_LAUNCH — RTL

### ICD-006: Autopilot → TelemetryListener
**Type:** MAVLink UDP
**Port:** 14552
**Messages consumed:**
- GLOBAL_POSITION_INT — lat, lon, alt
- VFR_HUD — airspeed, groundspeed, heading
- HEARTBEAT — mode, armed status
- MISSION_ITEM_REACHED — waypoint reached notification
