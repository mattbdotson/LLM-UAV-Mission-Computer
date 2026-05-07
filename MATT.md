# LLM-UAV Mission Computer — Project Journal

> A research notebook, decision log, and project narrative.
> For technical reference (file paths, configs, schemas) see `CLAUDE.md`.

---

## What We're Building

A small Vision Language Model (VLM), running on a Jetson Orin Nano at the edge, acting as the **autonomy layer** for a fixed-wing UAV.

The autopilot still flies the aircraft. We don't try to replace control loops with a neural net. Instead, the VLM looks at a top-down map showing the aircraft's position, heading, and target, and answers the high-level question: *"what should we do next?"* The answer comes back as a pixel coordinate on the map — *"go here"* — which the executor translates into a MAVLink waypoint command.

It's a deliberately minimal contract:
- **Autopilot**: keeps the wings level, holds altitude, follows waypoints.
- **VLM**: decides which waypoint to issue next, given visual context.
- **Mission Manager**: glues the two together, captures telemetry, draws the map, parses VLM output.

---

## The Big Idea

**Research question:** *what can a small edge VLM do as an autonomous mission planner when given visual spatial context instead of raw GPS coordinates?*

The motivating insight came from text-only LLM testing. Llama 3.2 1B and 3B, given GPS coordinates and a mission objective, could understand intent (they'd issue an RTL when the mission was done — without being told to) but they could not do **coordinate geometry**. Asked to fly to a point 500m north of the current position, they'd repeatedly send the aircraft to its current location — they had no reliable internal model of "north of X by 500m" in lat/lon space.

That's a fundamental limitation of small models. Floating-point arithmetic on coordinates is not their strong suit. So we changed the question:

| Approach | What the model has to do |
|---|---|
| GPS coordinates | Compute target lat/lon from current lat/lon and a desired offset — **arithmetic** |
| Pixel coordinates | Look at a map image and point at where to go — **perception** |

VLMs are perception engines. Pixel-pointing plays to their strengths. The map already encodes spatial relationships; the model just has to look.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       DEV PC  (Windows + WSL2)                       │
│                                                                      │
│  ┌────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│  │  JSBSim    │───►│  ArduPlane SITL  │◄══►│   Mission Manager    │  │
│  │ (physics)  │    │ (full firmware)  │UDP │ ┌──────────────────┐ │  │
│  └────────────┘    └──────────────────┘14552│ │ TelemetryListener│ │  │
│                                              │ ├──────────────────┤ │
│                                              │ │ Planner          │ │
│                                              │ ├──────────────────┤ │
│                                              │ │ Executor         │ │
│                                              │ ├──────────────────┤ │
│                                              │ │ MapCompositor    │ │
│                                              │ └────────┬─────────┘ │
│                                              └──────────┼───────────┘│
└─────────────────────────────────────────────────────────┼────────────┘
                                                          │
                                              HTTP        │  image (PNG/b64)
                                              POST        │  + prompt
                                                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PENNY ROYAL  (Jetson Orin Nano Super, 8GB)              │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  llama-server  (OpenAI-compatible API on :8080)                │  │
│  │  ┌──────────────────────┐    ┌──────────────────────────────┐  │  │
│  │  │  Gemma 4 E2B GGUF    │    │  mmproj (vision projector)   │  │  │
│  │  │  Q4_K_M quantization │    │  f16, image encoder          │  │  │
│  │  └──────────┬───────────┘    └──────────────┬───────────────┘  │  │
│  │             └────────────┬───────────────────┘                 │  │
│  │                          ▼                                     │  │
│  │             CUDA kernels (DGGML_CUDA=ON, all 99 layers)        │  │
│  └─────────────────────────┬──────────────────────────────────────┘  │
│                            ▼                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Ampere GPU — 1024 CUDA cores, 8GB unified memory              │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

The dev PC runs everything except inference. SITL is a full ArduPlane firmware build, not a model — it handles its own control loops, mode logic, mission state. The Mission Manager talks to SITL over MAVLink (UDP 14552) and to Penny Royal over HTTP. Penny Royal is *only* an inference server. It has no awareness of the aircraft, the mission, or the autopilot.

---

## Hardware

| Component | Details |
|---|---|
| **Dev PC** | Windows 11, WSL2 (Ubuntu 22.04). Hosts JSBSim, ArduPlane SITL, Mission Manager. |
| **Penny Royal** | NVIDIA Jetson Orin Nano Super Developer Kit. Named after the Polity AI in Neal Asher's novels. |
| · CPU/GPU | 6-core Arm Cortex-A78AE + 1024-core Ampere GPU. 8GB unified memory. |
| · OS | JetPack 6.2.2 / L4T 36.5. Recently upgraded from 36.4.7. |
| · Storage | 64GB microSD (current). NVMe Crucial P3 500GB ordered. |
| · Network | 192.168.1.177 on the home LAN. SSH'd from the dev PC. |
| **Autopilot** | ArduPlane SITL (virtualized). Real hardware planned. |
| **Airframe** | Simulated fixed-wing in JSBSim. No real airframe yet. |

The Orin Nano was deliberately chosen over the larger Orin NX. The constraint is the point: if it works on the smallest hardware, the deployment story is much easier. We pay for that with a tighter memory budget — Gemma 4 E4B doesn't fit, only E2B does.

---

## Software Stack

| Layer | Component | Role |
|---|---|---|
| Physics | JSBSim | Fixed-wing flight dynamics |
| Autopilot | ArduPlane SITL | Full firmware as a Linux process |
| GCS | MAVProxy | Console + map view, exposes MAVLink on UDP |
| Comms | pymavlink | Python MAVLink in the Mission Manager |
| Map data | OpenStreetMap | Base tile download via tile server |
| Image | Pillow | MapCompositor draws aircraft/trail/target overlays |
| HTTP | requests / Flask | Backend client + VILA server wrapper (written but never deployed — VILA abandoned before use) |
| Inference (active) | llama.cpp | Native CUDA build, OpenAI-compatible server |
| Inference (text trial) | Ollama | First attempted backend, blocked by CUDA bug |
| Inference (abandoned) | nano_llm + VILA 1.5-3B | Tried, dropped before deployment |
| Inference (future) | TensorRT | Placeholder backend for faster runtime |
| VLM (target) | Gemma 4 E2B + mmproj | Vision-capable, fits on Orin Nano |
| Config | python-dotenv | `.env` switches backend without touching code |

---

## Key Design Decisions

1. **SITL over HIL for now.**
   *Why:* we can iterate on planning logic without touching airframe hardware or risking flights. Full ArduPlane firmware runs as a Linux process — the autopilot logic is identical to what would run on a real Cube. Upgrade path is well-trodden.
   *Implication:* every architectural decision must remain valid when SITL is replaced by a real autopilot. No simulator-only shortcuts.

2. **LLM at the mission layer only.**
   *Why:* control-loop bandwidth is wrong for an LLM (we'd want kHz, the model gives us 0.1Hz). The autopilot is a mature, certified body of code. Replacing it with a neural net would be reckless and pointless.
   *Implication:* the VLM only ever issues high-level commands — `goto_pixel`, `loiter`, `rtl`. It never sets pitch, roll, throttle, or even a heading hold.

3. **Pixel coordinates over GPS.**
   *Why:* small models can't do coordinate arithmetic reliably (proven in text-only testing). They *can* point at things in images.
   *Implication:* the executor owns the pixel→GPS conversion using known map bounds. The VLM never sees lat/lon at all.

4. **Visual input via the MapCompositor.**
   *Why:* spatial context (where am I, where's the target, where have I been) is much richer in an image than in a telemetry dump. The model gets a unified scene rather than a list of numbers.
   *Implication:* every planning cycle pays the cost of rendering, encoding, and transmitting a PNG. That cost shapes the cycle time.

5. **Pluggable backend abstraction.**
   *Why:* the inference landscape is a moving target. We shouldn't have to touch mission code when we swap models or runtimes. The `InferenceBackend` ABC keeps `generate(system, user, image_b64) → str` stable; everything else is backend-specific.
   *Implication:* every new backend is a drop-in. We've already swapped Ollama → VILA → llama.cpp without changing `Planner`.

6. **Event-driven state machine — *notional, still being worked out*.**
   *Why:* the current planner runs every 10 seconds regardless of context. That's a placeholder. The right design is a state machine driven by autopilot events (waypoint reached, mode change, geofence breach) where the VLM is consulted at decision points, not on a timer.
   *Implication:* time-driven polling lets us iterate on the visual + prompt + parsing stack without yet committing to an event model. We'll migrate when the basics are stable.

---

## The Inference Backend Journey

A timeline of what we tried, what broke, and why:

```
Ollama + Llama 3.2 1B  ─────►  worked (text-only). No vision. Useful for
                                planner-loop integration testing.

Ollama + larger models  ─────►  CUDA memory bug in L4T 36.4.7. Models
                                >1B failed to load on GPU. Fell back to
                                CPU and timed out.

Ollama + moondream      ─────►  ran (Q2 quant) but poor instruction
                                following. Wouldn't reliably produce JSON.

Ollama + qwen2.5vl:3b   ─────►  too large for Ollama's allocator on Orin.
                                Same memory failure pattern.

Ollama + gemma4:e2b     ─────►  same allocator failure. Couldn't use GPU.

Ollama + gemma4:e4b     ─────►  too large for the Orin Nano regardless.

JetPack 36.4.7 → 36.5  ─────►  fixed the underlying CUDA bug. But Ollama
                                still couldn't use the GPU — its memory
                                model is wrong for unified memory.

llama.cpp built native  ─────►  the answer. Compiled with DGGML_CUDA=ON,
+ Gemma 4 E2B + mmproj         talks to the GPU directly. OpenAI-
                                compatible API on :8080. In progress.

VILA 1.5-3B via         ─────►  abandoned for disk space. nano_llm
nano_llm container             container is 12.7GB and the VILA
                                weights add another ~7GB. Together
                                they exceeded the free space on the
                                64GB SD card with the OS installed.
                                Not a technical failure — a storage
                                budget failure. By the time the NVMe
                                arrives, llama.cpp is the better path
                                anyway.
```

The lesson: **Ollama's UX advantage doesn't matter if it can't use the hardware.** The Orin Nano's unified memory architecture is where Ollama's allocator falls down. llama.cpp built natively with CUDA support is the right tool — less convenient, but it actually runs.

E2B vs E4B is the other constraint we've internalized. E4B simply does not fit. E2B does, with room for the vision projector. Future hardware (Orin NX) might let us run E4B, but we should design for E2B and treat anything bigger as upside.

---

## What We Learned From LLM Testing

From running text-only Llama 3.2 against orbit and figure-8 missions, before we had vision:

- **LLMs understand mission intent well.** Asked to fly an orbit, then return — they did, and issued the RTL on their own when they decided it was time. We did not have to prompt for that.
- **LLMs cannot do coordinate geometry.** Asked to fly 500m north of the target, they'd send the aircraft to the *current* position, repeatedly. The arithmetic is just unreliable.
- **The reasoning field is invaluable.** Every command carries a `reasoning` string. Reading those is how we figured out *why* the model kept sending us in circles. Without it, we'd be debugging blind.
- **Pixel coordinates dissolve the geometry problem.** Once we sketched the map-image approach, the path forward was obvious. The model doesn't compute offsets; it points.
- **Time-driven polling is a placeholder, not the goal.** A 10-second tick made sense for getting the loop working, but the model gives the same answer twice if nothing has changed. Decisions should be coupled to events.

---

## The Map System

The visual context pipeline:

```
OpenStreetMap tile server                     2304×2304 base tile
      │                                        (8 km × 8 km, Canberra)
      ▼
download_map.py ──────────►  assets/map_tile.png

                                                     ┌──────────────────┐
   telemetry (lat/lon/heading)  ─────────────────►   │  MapCompositor   │
                                                     │                  │
   mission target (lat/lon)     ─────────────────►   │  • copy base     │
                                                     │  • draw trail    │
   trail history (last 50 pts)  ─────────────────►   │  • draw target   │
                                                     │  • draw aircraft │
                                                     │  • compass rose  │
                                                     │  • resize 384²   │
                                                     │  • PNG → base64  │
                                                     └────────┬─────────┘
                                                              │
                                                              ▼
                                                    image_b64 to VLM
```

Visual conventions on the rendered map:
- **Blue arrow** — aircraft position and heading
- **Blue line** — recent flight trail (last 50 telemetry points)
- **Red crosshair** — mission target
- **Compass rose** — top-left corner

The base tile is rendered once; per-cycle work is just the overlay. Resize-to-VLM-size happens last so we always draw at full resolution and downscale with LANCZOS.

The VLM responds with pixel coordinates. The Executor calls `MapCompositor.pixel_to_gps(x, y)` to convert back, then issues a MAVLink waypoint command. **The VLM never sees lat/lon.**

---

## Planned Architecture Evolution

### Current — naive time-driven polling

```
┌──────────────┐
│ telemetry    │  every 0.1s, drain MAVLink queue
│ update       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ has 10s      │ ─── no ──► continue polling
│ elapsed?     │
└──────┬───────┘
       │ yes
       ▼
┌──────────────┐
│ compose map  │
│ call VLM     │
│ exec command │
└──────────────┘
```

The model is asked the same question every 10 seconds whether anything has changed or not. This is fine for development — it makes the loop trivial to reason about — but it's not the design we'll ship.

### Target — event-driven state machine *(notional)*

The states, transitions, and trigger events below are a working sketch. Expect them to change as we figure out the right granularity.


```
                    ┌─────────────┐
                    │  PREFLIGHT  │
                    └──────┬──────┘
                           │ arm + takeoff issued
                           ▼
                    ┌─────────────┐
                    │   TAKEOFF   │
                    └──────┬──────┘
                           │ cruise altitude reached
                           ▼
            ┌────────► ┌─────────────┐
            │          │   TRANSIT   │
            │          └──────┬──────┘
            │                 │ near task area
            │                 ▼
            │          ┌─────────────┐
   task     │          │   ON_TASK   │
   continues│          └──────┬──────┘
            └─────────────────┤
                              │ task complete
                              ▼
                       ┌─────────────┐
                       │  RETURNING  │
                       └──────┬──────┘
                              │ landing complete / disarm
                              ▼
                       ┌─────────────┐
                       │   LANDED    │
                       └─────────────┘
```

The VLM is only consulted at **state transitions** and at **anomalies** — geofence breaches, low fuel, mission timeouts. Telemetry events drive the machine; the model isn't asked the same question over and over while nothing changes.

This buys us:
- **Lower inference cost** — fewer calls per mission
- **Sharper context** — each call is at a meaningful moment, with a meaningful question
- **Better debug logs** — every VLM call is tied to a specific event

### State Machine as LLM Memory

The state machine solves a second problem beyond event-driven triggering: **it gives the LLM persistent memory across the mission.**

Currently every LLM call is stateless — the model gets raw telemetry and has no idea what happened before. The state machine can accumulate a context object that grows throughout the mission:

```python
mission_context = {
    "objective": "Search grid A3 for targets of interest",
    "waypoints_visited": [
        {"seq": 1, "finding": "nothing notable"},
        {"seq": 2, "finding": "investigated structure — false positive"}
    ],
    "decisions_made": [
        {"trigger": "waypoint_reached", "seq": 2, "decision": "investigate",
         "reasoning": "unusual structure visible on map"}
    ],
    "time_on_task_seconds": 420
}
```

Every LLM decision gets stored in this context. The next call includes the full history. The model can now reason about patterns across the mission — *"I've investigated two things and both were false positives, I'll set a higher bar"* — rather than treating each waypoint as if it's the first.

This is the architectural insight that makes the LLM **genuinely useful rather than reactive**: the state machine converts the time-driven telemetry stream into meaningful events, AND provides the memory layer that small models lack natively.

---

## Open Questions / Research Directions

- **Can E2B reliably output valid JSON with pixel coordinates?** Gemma 4 has native JSON/function calling support baked in — higher confidence than moondream — but unproven on our specific task.
- **Does visual context actually beat text-only?** We expect yes (that's the whole thesis), but we should measure it. Same mission, same model, with and without the map image — what's the difference?
- **What's the right event granularity for state-machine triggers?** Every waypoint reached? Every mode change? Every N seconds with no event? We don't know yet.
- **Does state machine memory improve decision quality?** If we feed prior waypoint findings and decisions into the prompt, does the model make better choices? Or does the added context confuse it?
- **Can the model learn mission patterns with accumulated context?** If we feed prior decisions and outcomes into the prompt, does it get better at this mission over time? Or just confused?
- **X-Plane integration for photorealistic visual input?** SITL gives us a top-down OpenStreetMap tile. X-Plane could give us a real downward-facing camera feed. Different problem, more interesting answers.

---

## Future Hardware Upgrades

| Upgrade | Effect |
|---|---|
| NVMe SSD (Crucial P3 500GB, ordered) | Faster Docker pulls, room for multiple model variants, no more wedging the 64GB SD card |
| Real autopilot (Cube Orange+ / Matek H743) | HIL testing — same firmware, real radio, real GCS |
| Jetson Orin NX | Doubles the memory headroom, opens up E4B and Qwen2.5-VL 7B |
| Real airframe | Eventually — when the planning stack is trustworthy enough to risk flying |

Order matters. NVMe and a real autopilot come before the airframe. Trust the software in HIL before you trust it in flight.

---

## Session Log

| Date | Session | What landed |
|---|---|---|
| **2026-04-20** | 1 | Project setup. GitHub repo. `mission_manager/` skeleton. WSL2 environment. CLAUDE.md scaffolded. |
| **2026-04-23** | 2 | TelemetryListener, Planner, Executor. First autonomous flight in SITL — armed, took off, hit a waypoint, RTL. |
| **2026-05-02** | 3 | LLM integration via Ollama. Stub planner replaced with real planner calling Llama 3.2. Arm/takeoff sequence shaken out. First text-only mission decisions. |
| **2026-05-03** | 4 | MapCompositor. VLM architecture (pixel coordinates, image input). VILA wrapper sketched. The pivot from GPS prompts to visual prompts. |
| **2026-05-06** | 5 | Backend abstraction (`InferenceBackend` ABC). Code review pass — bug fixes across `main.py`, `executor.py`, `map_compositor.py`, `download_map.py`. Switched OllamaBackend to `/api/chat` for vision. Moondream tested, found wanting. JetPack upgrade. llama.cpp backend added. Gemma 4 E2B chosen. CLAUDE.md restructured with the inference backend history. This journal added. |

---

*Last updated: end of Session 5, 2026-05-06.*
