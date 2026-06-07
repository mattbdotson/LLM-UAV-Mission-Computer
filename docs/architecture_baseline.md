# LLM-UAV-Mission-Computer V1.0 — Architecture Baseline

## Document Control
- Architecture name: **LLM-UAV-Mission-Computer V1.0**
- Version: 1.0
- Status: Baseline (frozen)
- Last updated: 2026-06-06
- Git reference: `v1.0` (tag the working flight core before V2.0 perception/3D work begins)
- Successor: **V2.0** — the perception / onboard-camera / 3D-simulation build (see §13)

## Purpose

This document captures the **as-built** architecture of the LLM-UAV Mission Computer at the point immediately before the perception / 3D-environment expansion. This frozen baseline is designated **V1.0**; the expansion that follows is **V2.0**. This is a reference, not a design proposal. Its job is to record what exists and works today — including its quirks, embedded fixes, and known limitations — so that V2.0 (onboard camera, visual detection, geo-projection, navigation subsystem) can be defined against an accurate, agreed snapshot rather than a reconstruction from memory.

Where this document and `CLAUDE.md` disagree, **this document reflects the code**; drift between the two is recorded explicitly in §12.

## Scope

In scope: the runtime system that flies autonomous missions in SITL today — the mission manager, its inference backends, the map/coordinate model, the state machine, and the MAVLink command interface.

Out of scope (deliberately — these define **V2.0**, see §13): onboard camera, visual object/landmark detection, pixel-to-ground geo-projection, a dedicated navigation subsystem, GPS-denied navigation, terrain following, and any 3D simulation backend.

---

## 1. Research Context

The system exists to investigate a single question: **what can a small edge vision-language model do as an autonomous mission planner when given visual spatial context and stripped of textual answer keys?** The VLM is not a component to be optimized away — in the baseline it *is* the object of study. Every design choice that looks inefficient (pixel coordinates instead of GPS math, no injected phase state, deliberately vague mission text) exists to keep genuine visual and spatial reasoning as the thing being measured.

This framing is load-bearing for interpreting the baseline. The system is not engineered to be the best possible autonomy stack; it is engineered to isolate and observe a 2B VLM's reasoning.

---

## 2. System Context

The system runs as a two-host arrangement. In the current baseline, all simulation and orchestration run on the development PC; only model inference is offloaded to the edge device.

| Host | Role in baseline | Sim-vs-real character |
|---|---|---|
| **Wintermute** (dev PC, Windows + WSL2, RTX 4060 Ti) | Runs ArduPlane SITL, MAVProxy, and the entire mission manager process | Simulation + orchestration |
| **Pennyroyal** (Jetson Orin Nano Super, 8 GB unified) | Runs the VLM inference server (`llama-server`) only | Edge inference (representative of flight hardware) |

The mission manager talks to the autopilot over MAVLink (UDP) and to the inference server over HTTP. The only external data dependency is a pre-downloaded OpenStreetMap tile of the SITL operating area (Canberra); there is no live map fetching during a mission.

---

## 3. Deployment / Runtime Topology

```
WINTERMUTE (dev PC, WSL2)                          PENNYROYAL (Jetson Orin Nano)
──────────────────────────────────────            ─────────────────────────────
sim_vehicle.py -v ArduPlane -f plane               llama-server (native llama.cpp
  ├─ ArduPlane firmware (SITL)                        build 9468 / commit 354ebac8c,
  ├─ built-in plane flight model                      CUDA 12.6, arch sm_87)
  └─ MAVProxy (--console --map)                        ├─ Gemma 4 E2B (Q8_0)
        │  --out udp:localhost:14552                   └─ mmproj Q8_0 (vision)
        │                                               served on :8080
        ▼                                                     ▲
mission_manager (main.py)                                     │ HTTP POST
  telemetry ─ event_monitor ─ state_machine                   │ (system+user prompt
  ─ planner ─ executor ─ map_compositor ────────────────────┘  + base64 map image)
        │
        └─ MAVLink commands  ──► udp:localhost:14552 ──► autopilot
```

Note: the `INFERENCE_BACKEND` env var selects the backend. The code default is `vila` (waits on port 5000), but the **active deployment uses the llama.cpp backend** pointing at `llama-server` on Pennyroyal:8080. See §12.

---

## 4. Software Architecture

The mission manager is a single Python process organized into packages under `mission_manager/`. Total ~1,500 lines. Components and responsibilities:

| Component | File | Lines | Responsibility |
|---|---|---|---|
| Entry point / orchestration | `main.py` | 112 | Launches SITL, wires components, runs the 0.1 s poll loop, holds the mission objective string |
| Telemetry listener | `core/telemetry.py` | 45 | Drains MAVLink, maintains current state dict (lat/lon/alt/heading/speed/mode/armed), buffers raw messages |
| Event monitor | `core/event_monitor.py` | 48 | Derives events (`altitude_reached`, `waypoint_reached`, `mode_changed`, `no_progress`) from raw MAVLink |
| State machine | `core/state_machine.py` | 110 | 7-state mission lifecycle; routes events; invokes the planner at decision points |
| Planner | `core/planner.py` | 222 | Composes prompt + map image, calls the inference backend, parses the decision JSON, archives every run |
| Executor | `core/executor.py` | 150 | Arm/takeoff sequence; translates decisions into MAVLink (`goto_pixel`, `goto_waypoint`, `loiter`, `fly_waypoints`, `rtl`) |
| Mission context | `core/mission_context.py` | 75 | Holds objective, decision history, scratchpad fields; appends `decisions.jsonl` |
| Map compositor | `mapping/map_compositor.py` | 116 | Renders the VLM input image (tile + aircraft marker/trail/target); owns `pixel↔gps` conversion |
| Map downloader | `mapping/download_map.py` | 90 | One-time OSM tile fetch + `map_config.py` generation (not used during missions) |
| Inference backends | `backends/*.py` | ~240 | `base.py` ABC + `llamacpp` (active), `vila`, `ollama`, `tensorrt` (empty stub) |
| Config | `config/map_config.py` | 18 | Fixed map tile path, geographic bounds, mission target, VLM image size |
| Prompts | `prompts/*.txt` | — | System prompt + per-event templates (`transit_started`, `waypoint_reached`, `stuck`) |

### Inference backend abstraction

`backends/base.py` defines an `InferenceBackend` ABC with three methods: `generate(system_prompt, user_prompt, image_b64) → str`, `health_check() → bool`, `get_name() → str`. Backends are interchangeable behind this contract. This factory pattern is the cleanest extension point in the codebase and is the natural template for the future `FrameSource` / `Detector` abstractions. `tensorrt_backend.py` exists as a 0-line placeholder — reserved, never implemented.

---

## 5. Control & Data Flow (the decision cycle)

The system is **event-driven, not continuous**. The main loop polls MAVLink every 100 ms but the VLM is invoked only at discrete decision points. A single decision cycle:

1. `telemetry.update()` drains all pending MAVLink messages, updates the state dict, buffers raw messages.
2. `event_monitor.check(raw_messages)` inspects the buffer and the elapsed-time clock, firing at most one event.
3. The event is dispatched to `state_machine.on_event(...)`, routed by reflection to a `handle_<event>` method.
4. If the handler decides a planning step is needed, it calls `planner.decide_with_context(state, context, event, event_data)`.
5. The planner composites the current map image, fills the relevant prompt template, POSTs to the inference backend, and parses the returned JSON decision (stripping markdown fences if present).
6. The decision (command, reasoning, params, scratchpad `progress`/`next_intent`) is recorded to `MissionContext` and appended to `decisions.jsonl`; the map image is saved to the debug directory.
7. `executor.execute(command)` converts the decision into MAVLink and sends it to the autopilot.

Key property: the VLM never participates in any fast control loop. The autopilot owns flight; the VLM is consulted between waypoints. "Real-time" for this system means "responsive between decision points," a soft constraint.

---

## 6. State Machine

States (`core/state_machine.py`):

```
PREFLIGHT → TAKEOFF → TRANSIT → ON_TASK ⇄ STUCK → RETURNING → LANDED
```

| Event | Source | Effect |
|---|---|---|
| `altitude_reached` | rel-alt crosses 50 m | TAKEOFF → TRANSIT; first LLM call (`transit_started`) |
| `waypoint_reached` | `MISSION_ITEM_REACHED` | TRANSIT → ON_TASK (first time); thereafter LLM call (`waypoint_reached`); from STUCK → ON_TASK + LLM call |
| `no_progress` | 600 s elapsed since last waypoint, airborne | ON_TASK → STUCK; LLM call (`stuck`) |
| `mode_changed` | `HEARTBEAT` custom_mode | In RETURNING, mode 9 (LAND) → LANDED |

Hard-coded (non-LLM) behaviors embedded in the state machine, important to record:
- **Auto-RTL boundary heuristic**: in ON_TASK, if `pixel_y < 20` (near northern map edge), the state machine issues RTL directly and transitions to RETURNING **without consulting the VLM**. This couples a navigation decision into the state machine.
- An `rtl` command from the planner transitions to RETURNING.

---

## 7. Command & Interface Specification

### Decision JSON schema (VLM output, parsed by planner)

```json
{
  "command": "goto_pixel | goto_waypoint | loiter | fly_waypoints | rtl",
  "reasoning": "free-text chain-of-thought summary",
  "params": { "x": 0-511, "y": 0-511, "alt": 100, ... },
  "progress": "free-text scratchpad (optional)",
  "next_intent": "free-text scratchpad (optional)"
}
```

### Commands the executor honors (`core/executor.py`)

| Command | Params | MAVLink action |
|---|---|---|
| `goto_pixel` | `x,y` (clamped 0–511), `alt` | `pixel_to_gps()` → GUIDED + `MISSION_ITEM_INT` waypoint |
| `goto_waypoint` | `lat,lon,alt` | GUIDED + `MISSION_ITEM_INT` waypoint |
| `loiter` | `x,y` or `lat,lon`, `alt`, `radius` (def 500) | `NAV_LOITER_UNLIM` |
| `fly_waypoints` | list of `{lat,lon,alt}` | sequential `MISSION_ITEM_INT` |
| `rtl` | — | `NAV_RETURN_TO_LAUNCH` |

Altitude floor of 50 m is enforced on `goto_pixel` and `goto_waypoint` only (both route through `_goto_waypoint`); `loiter` and `fly_waypoints` send their altitude directly and bypass the floor. Unknown commands are logged and ignored.

### Inference interface

HTTP POST to the backend (`llama-server` on :8080 in deployment): system prompt + user prompt + base64-encoded 512×512 map image. Thinking mode enabled, 3000-token budget; a typical decision consumes 400–1000 thinking tokens. If the model fails to emit valid JSON within budget, the planner falls back to RTL.

### Arm / takeoff sequence (`executor.arm_and_takeoff`)

GUIDED → arm (force flag `21196`) → TAKEOFF mode (10 s) → back to GUIDED. The sequence is timing-based (`sleep`) and the force-arm magic number is required for SITL. Connection string: `udp:localhost:14552`.

---

## 8. Coordinate & Map Model

The VLM reasons in a fixed 512×512 pixel frame mapped linearly to a fixed geographic bounding box (`config/map_config.py`):

- Tile: pre-downloaded OSM raster of the Canberra SITL area (`assets/map_tile_osm.png`).
- Bounds: lat `[-35.3890, -35.3443]`, lon `[149.1394, 149.1943]`.
- `pixel_to_gps` / `gps_to_pixel`: linear interpolation across these bounds (no projection correction; acceptable over this small extent).
- VLM image size: 512×512 (model-specific; set for Gemma 4).

The compositor draws the aircraft position/heading, its trail, and the mission target onto the tile. This single artifact currently serves two distinct roles — geographic reference frame **and** the VLM's perceptual input — which is the coupling V2.0 will split.

---

## 9. Key Mechanisms & Design Invariants

- **Stripped prompts (no answer key)**: named landmarks and explicit coordinates are removed from all active prompts. The prominent road is referred to only as "the prominent road that runs north-south through the area." Re-introducing names or coordinates would let the model solve by text arithmetic and invalidate the research question. This is a hard invariant, not a preference.
- **Two-step visual grounding**: the system prompt requires the model to describe what is visible at its current position and at its intended destination before emitting a command, forcing a visual description ahead of coordinates.
- **Pixel-coordinate indirection**: the VLM emits pixels, never GPS. The executor owns the pixel→GPS conversion. This removes coordinate arithmetic (which the 2B model cannot do reliably) from the model's job.
- **Model-authored scratchpad**: `progress` and `next_intent` free-text fields are stored verbatim and surfaced back on the next call. The system never interprets, validates, or modifies them — injecting structured phase state would be an answer key by another door. Wrong beliefs propagating is treated as signal, not a bug.
- **Per-run archiving**: every run creates `debug/maps/<run_id>/` (saved map images per decision) and `missions/<run_id>/` (prompts + `decisions.jsonl`). Both directories are git-ignored, so artifacts are local-only and never committed.

---

## 10. Proven Capabilities (baseline truth)

From `docs/results.md`, established at the baseline:

- **Complete takeoff-to-RTL mission cycle** achieved (run `20260602_205327`, six LLM calls, no crashes).
- **Genuine visual grounding** demonstrated at least once (run `20260601_232846`): located the unnamed north-south road by inspection at x≈300–320, read a place name ("Jerrabomberra Nature Reserve") off the tile, inferred phase transitions statelessly.
- **Scratchpad eliminates phase regression**: phase progression held across all decisions with the scratchpad enabled, where three prior runs regressed.
- **First RTL emission** and a documented instance of the model self-correcting against its own scratchpad on visual evidence.
- **Stable inference**: native llama.cpp + Q8_0 + `--cache-ram 0` stable across 6+ sequential multimodal calls.

---

## 11. Known Limitations & Failure Modes

From `docs/results.md` and `docs/troubleshooting.md`:

- **Road-following is not a demonstrated behavior.** In the RTL run the model collapsed two phases into a diagonal and crossed the road transversely; apparent alignment occurred only because both endpoints already lay on the road. The most-wanted spatial behavior is unproven.
- **Capability is not reproducible across runs.** Genuine road identification appeared in one run and was absent in the next under near-identical conditions — consistent with operating at the model's noise floor.
- **Confabulation.** The model sometimes fabricates visual descriptions (`(Simulated based on the provided image)` observed in CoT). A structural 2B-scale property, not prompt-addressable.
- **No native working memory.** Phase continuity exists only because of the external scratchpad scaffold; the scratchpad itself can compound wrong beliefs.
- **False `no_progress`.** The fixed-time threshold can fire during legitimate long legs; mitigated to 600 s, with a distance-based check deferred.
- **Model ceiling on hardware.** E4B OOMs on vision inference in 8 GB; E2B is the confirmed ceiling for this box.

---

## 12. Known Drift & Technical Debt

Drift identified at the V1.0 freeze, split by disposition so V2.0 doesn't inherit confusion.

**Corrected at the V1.0 freeze (documentation-only, no behavior change):**

- **FDM mismatch**: `CLAUDE.md` previously stated the stack uses JSBSim; the code launches `sim_vehicle.py -f plane` (ArduPilot's built-in plane model). Corrected in `CLAUDE.md` to match the code.
- **Backend default comment**: the comment around `INFERENCE_BACKEND` implied `vila` is the operative backend; the active model is Gemma 4 E2B via the llama.cpp backend on :8080 (the env var is overridden in deployment). Comment corrected. The code default value is unchanged.

**Retained as documented debt (behavior/artifacts frozen; deferred to V2.0):**

- **Coupled navigation in the state machine**: the auto-RTL at `pixel_y < 20` is a hard-coded navigation decision living in the state machine rather than in the planner or executor.
- **Empty TensorRT stub**: `backends/tensorrt_backend.py` is a 0-line placeholder.
- **Single fixed map**: bounds and tile are hard-coded to one Canberra area; missions are not portable to other regions without regenerating `map_config.py`.
- **Timing-based arm/takeoff**: `sleep`-based sequencing is brittle but functional in SITL.
- **Stale inference helper script**: `scripts/start_inference_server.sh` diverges from the as-flown V1.0 config — it specifies `Q4_K_M` weights and a `BF16` mmproj, `-c 2048`, and `--image-{min,max}-tokens 256`, and it omits the mandatory `--cache-ram 0` and `--parallel 1`. It is a manual helper, not invoked by `main.py`. The authoritative launch configuration is §14 and `inference_setup.md`. Recommend a separate post-freeze fix, as the missing `--cache-ram 0` reproduces the documented OOM (see §11, troubleshooting.md).

---

## 13. V1.0 → V2.0 Boundary (what V1.0 deliberately excludes)

The following do not exist in V1.0 and define the **V2.0** architecture work:

- Onboard camera as an input modality (the VLM perceives a cartographic map, not a rendered scene).
- Visual object / landmark detection (no perception service).
- Pixel-to-ground geo-projection of detections.
- A dedicated navigation subsystem separating coordinate math from the VLM's view.
- GPS-denied navigation, map-matching localization, terrain following.
- Any 3D simulation backend (Gazebo, etc.); the world is a flat OSM raster.

The agreed direction for V2.0: a continuous perception service on the edge device (detector + geo-projector) writing georeferenced detections into a world-state registry; the map compositor split into a high-fidelity NavMap (coordinate math) and a deliberately schematic VLMView (the VLM's input); the VLM retained as the event-driven reasoning/prioritization layer, not the perception engine. The V1.0 invariants in §9 — above all the stripped-prompt rule — carry forward into V2.0 and must not be eroded by the introduction of detected/labeled features.

---

## 14. V1.0 Baseline Snapshot Reference

| Item | Value |
|---|---|
| Architecture name | LLM-UAV-Mission-Computer V1.0 |
| Git tag | `v1.0` |
| Model | Gemma 4 E2B, Q8_0 weights + Q8_0 mmproj |
| Inference engine | native llama.cpp, build 9468 / commit `354ebac8c`, CUDA 12.6, `sm_87` |
| Server flags | `-c 4096 --parallel 1 --cache-ram 0` |
| FDM | ArduPlane SITL built-in plane model (`-f plane`) |
| VLM image | 512×512, base64 over HTTP |
| Thinking budget | 3000 tokens |
| No-progress timeout | 600 s |
| Waypoint altitude floor | 50 m |
| Map | fixed OSM tile, Canberra; linear pixel↔gps over fixed bounds |
| Decision schema | `command`, `reasoning`, `params`, `progress`, `next_intent` |
| Commands | `goto_pixel`, `goto_waypoint`, `loiter`, `fly_waypoints`, `rtl` |
| Hosts | Wintermute (SITL + mission manager), Pennyroyal (inference) |

### Embedded operational knowledge (do not re-derive)

`--cache-ram 0` is mandatory (unbounded prompt-cache growth otherwise). JSON markdown-fence stripping in `llamacpp_backend.py` is required (Gemma wraps output). Arm force flag `21196` is required for SITL. The GUIDED → TAKEOFF → GUIDED dance is required for takeoff. The NVIDIA Docker llama.cpp image has a memory defect (crash on ~3rd call) — native builds only. A server crash leaks 30–300 MB until reboot.
