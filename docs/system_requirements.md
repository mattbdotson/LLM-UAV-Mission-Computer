# System Requirements

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: SITL simulation phase only
- Last updated: 2026-05-07

## 1. Mission Requirements

| ID | Requirement |
|---|---|
| MIS-001 | The system SHALL execute multi-phase missions defined by a natural language objective |
| MIS-002 | The system SHALL use a VLM to make mission decisions from visual map input |
| MIS-003 | The system SHALL maintain a decision log capturing command and reasoning for every LLM call |
| MIS-004 | The system SHALL support mission objectives expressed as pixel coordinate navigation |
| MIS-005 | The system SHALL support multi-phase missions with conditional phase transitions |
| MIS-006 | The system SHALL track completed mission phases explicitly and pass them to the LLM in every prompt |
| MIS-007 | The system SHALL detect phase completion based on pixel position thresholds defined per mission |

## 2. Safety Requirements

| ID | Requirement |
|---|---|
| SAF-001 | The system SHALL NOT command control surface inputs directly — all flight control SHALL be delegated to the autopilot |
| SAF-002 | The system SHALL NOT override autopilot safety modes |
| SAF-003 | The system SHALL command RTL if VLM inference fails after one retry |
| SAF-004 | The system SHALL command RTL if map image composition fails |
| SAF-005 | The system SHALL transition to STUCK state after 60 seconds without waypoint progress |
| SAF-006 | The system SHALL command RTL or continue mission from STUCK state based on LLM assessment |
| SAF-007 | The system SHALL NOT arm the aircraft unless the VLM backend health check passes (future — not yet implemented) |
| SAF-008 | The system SHALL NOT start the no_progress timer until the first ON_TASK waypoint has been reached |

## 3. Performance Requirements

| ID | Requirement |
|---|---|
| PER-001 | The system SHALL make a planning decision within 120 seconds of a triggering event |
| PER-002 | The system SHALL generate a map image for every LLM call |
| PER-003 | The system SHALL save debug map images for every LLM call |
| PER-004 | The system SHALL archive mission prompts and metadata for every flight |

## 4. Interface Requirements

| ID | Requirement |
|---|---|
| INT-001 | The system SHALL communicate with the autopilot exclusively via MAVLink UDP |
| INT-002 | The system SHALL communicate with the VLM exclusively via HTTP |
| INT-003 | The system SHALL support any OpenAI-compatible inference backend via the backend abstraction layer |
| INT-004 | The system SHALL accept backend configuration via environment variables without code changes |
| INT-005 | The system SHALL consume all MAVLink messages through a single connection owner (TelemetryListener) |

## 5. Out of Scope (SITL Phase)

The following are explicitly out of scope for the current SITL phase:
- Battery monitoring and low-battery RTL
- Comms loss detection
- Geofence enforcement
- Sensor failure detection
- Multi-aircraft coordination
