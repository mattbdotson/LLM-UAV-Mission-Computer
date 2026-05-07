# LLM-UAV Mission Computer — Project Journal

## How to Use This Document

This is a living research notebook. It documents not just what was built but **why** decisions were made, what was learned, and what failed. Each chapter is self-contained.

- **Chapters 1–4** — Foundational. Written once, updated when fundamentals change.
- **Chapters 5–7** — Living. Updated as the project evolves.
- **Chapters 8–9** — Critical. Safety and results, increasingly important as we approach real hardware.
- **Chapter 10** — Running log. Updated every session.

For technical reference (file paths, configs, API schemas, environment variables) see `CLAUDE.md`.

---

# Chapter 1: Vision & Research Question

## What We're Building

A small Vision Language Model (VLM), running on a Jetson Orin Nano at the edge, acting as the **autonomy layer** for a fixed-wing UAV.

The autopilot still flies the aircraft. We don't try to replace control loops with a neural net. Instead, the VLM looks at a top-down map showing the aircraft's position, heading, and target, and answers the high-level question: *"what should we do next?"* The answer comes back as a pixel coordinate on the map — *"go here"* — which the executor translates into a MAVLink waypoint command.

It's a deliberately minimal contract:
- **Autopilot**: keeps the wings level, holds altitude, follows waypoints.
- **VLM**: decides which waypoint to issue next, given visual context.
- **Mission Manager**: glues the two together, captures telemetry, draws the map, parses VLM output.

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

# Chapter 2: System Architecture

> *This chapter reflects the **current** architecture. Major architectural changes are documented in Chapter 10 (Session Log) with the date they were introduced.*

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

## Architecture Evolution Path

The system is designed to scale through phases without changing the core contract between the Mission Manager and the inference layer:

| Phase | Configuration | What changes | What stays the same |
|---|---|---|---|
| **1 (current)** | Dev PC + ArduPlane SITL + Penny Royal (Gemma 4 E2B) | — | — |
| **2** | Dev PC + ArduPlane SITL + Penny Royal (larger model via NVMe) | Model size, possibly resolution | All interfaces |
| **3** | Dev PC + X-Plane + Penny Royal (photorealistic visual input) | Visual source: rendered map → real camera frames | MAVLink, backend ABC, command schema |
| **4** | Dev PC + ArduPlane HIL + real autopilot + Penny Royal | Autopilot is real hardware over serial/USB | Mission Manager, VLM, prompts |
| **5** | Real airframe + Penny Royal (fully embedded) | Mission Manager runs on Penny Royal, no dev PC | Same VLM, same prompts, same schema |

The pluggable backend abstraction and the pixel-coordinate command schema are the two architectural decisions that survive every phase. Everything else is allowed to change.

---

# Chapter 3: Hardware

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

## Hardware Evolution Log

| Date | Component | Change | Reason |
|---|---|---|---|
| 2026-04-20 | Penny Royal | Initial setup with 64GB SD, JetPack 6.2 | Project start |
| 2026-05-06 | Penny Royal | JetPack upgraded to 6.2.2 (L4T 36.5) | Fix CUDA memory allocation bug |
| 2026-05-xx | Penny Royal | NVMe SSD installed (Crucial P3 500GB) | SD card too small for large containers |

## Planned Hardware

| Upgrade | Effect |
|---|---|
| NVMe SSD (Crucial P3 500GB, ordered) | Faster Docker pulls, room for multiple model variants, no more wedging the 64GB SD card |
| Real autopilot (Cube Orange+ / Matek H743) | HIL testing — same firmware, real radio, real GCS |
| Jetson Orin NX | Doubles the memory headroom, opens up E4B and Qwen2.5-VL 7B |
| Real airframe | Eventually — when the planning stack is trustworthy enough to risk flying |

Order matters. NVMe and a real autopilot come before the airframe. Trust the software in HIL before you trust it in flight.

---

# Chapter 4: Software Design

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

## Prompting Strategy Decision

*Date: 2026-05-07*

We evaluated three prompting strategies for LLM decision points in the state machine:

**Option A — Focused prompt per event type.** Rejected. Does not scale once anomalies are introduced — the event space becomes too large to maintain individual prompts for each case.

**Option B — Universal prompt with event context (selected).** One prompt template populated with current state, triggering event, mission history, and map image. The LLM receives full context and responds with a command from the available action set. Selected for initial implementation because it handles unexpected events gracefully and is flexible enough to iterate on without restructuring the prompting system.

**Option C — Action menu constrained per state.** Most architecturally interesting — constrains LLM output to only legal actions for the current state, reducing hallucination risk and parse complexity. Deferred. If Option B produces unreliable JSON or poor decision quality, migrate to C. The state machine architecture already supports this — legal actions per state are implicit in the transition table and can be made explicit in prompts without changing the executor.

The hybrid approach worth exploring under Option C: validate that the LLM's named command is legal for the current state, and reject/fallback if not. This gives output flexibility with machine-enforced constraints.

---

# Chapter 5: Inference Backend Comparison

> *Living chapter. When a new model is tested, add a row to the table and a narrative entry below.*

## Comparison Table

| Model | Backend | Size | Vision | JSON Output | GPU on Orin Nano | Status | Notes |
|---|---|---|---|---|---|---|---|
| llama3.2:1b | Ollama | 1GB | No | Good | No (CPU only) | Abandoned | Useful for pipeline testing |
| llama3.2:3b | Ollama | 2GB | No | Good | No (CPU only) | Abandoned | CUDA bug |
| moondream | Ollama | 1.7GB | Yes | Poor | No (CPU only) | Abandoned | Garbage JSON output |
| qwen2.5vl:3b | Ollama | 2GB | Yes | Good | No (OOM) | Abandoned | Too large for Ollama allocator |
| gemma4:e2b | Ollama | 1.5GB | Yes | Native | No (CPU only) | Abandoned | Ollama can't use GPU |
| gemma4:e4b | Ollama | 5GB | Yes | Native | No (OOM) | Abandoned | Too large for Orin Nano entirely |
| Gemma 4 E2B | llama.cpp native | 1.5GB | Yes | Native | Yes (in progress) | Active | Correct path |
| VILA 1.5-3B | nano_llm | 7GB | Yes | Good | Unknown | Abandoned | Disk space constraint |

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

# Chapter 6: Mission Results

> *This chapter is currently empty. It will be populated as missions are flown.*
> *First real entry expected after llama.cpp + Gemma 4 E2B vision is confirmed working.*

## Mission Result Template

When a mission completes, copy this template and fill it in:

```
### Mission [N] — [short name]

- **Date:**
- **Simulation backend:** (SITL / X-Plane / HIL / Real)
- **VLM model and backend:**
- **Mission objective:**
- **System prompt used:** (or link to prompts/ file at the relevant commit)
- **Outcome:** (success / partial / failure)
- **VLM decision log:** (paste reasoning fields from terminal output)
- **Flight path visualization:** (embed plot if available)
- **Key observations:**
- **Changes made as a result:**
```

## Mission Log

*(empty)*

---

# Chapter 7: Lessons Learned

> *Running list of non-obvious insights. Add entries as they're discovered. Each entry includes the date so we can see how our understanding evolved.*

1. **LLMs understand mission intent but cannot do coordinate arithmetic.** They'll issue an RTL when the mission is done without being prompted, but ask them to fly 500m north and they send the aircraft to its current position. *(Discovered: May 2026, text-only testing.)*

2. **Pixel coordinates solve the geometry problem.** VLMs are perception engines, not calculators. Pointing at an image works; computing a lat/lon offset does not. *(Discovered: May 2026.)*

3. **The reasoning field is essential for debugging.** Without it you're flying blind — you can see the command but not why the model chose it. *(Discovered: May 2026.)*

4. **Ollama cannot use the Jetson GPU regardless of firmware version.** The allocator is wrong for unified memory. llama.cpp built natively with `DGGML_CUDA=ON` is the correct path. *(Discovered: May 2026.)*

5. **E4B does not fit on Orin Nano. E2B does.** Design for E2B and treat anything bigger as upside. *(Discovered: May 2026.)*

6. **Time-driven planning is a placeholder.** Asking the model the same question every 10 seconds while nothing has changed wastes inference and produces redundant decisions. Event-driven state machine is the target architecture. *(Insight: May 2026.)*

7. **The state machine is also the LLM's memory layer.** Accumulating mission context across decision points solves the statelessness problem in a way that simply enlarging the prompt does not. *(Insight: May 2026.)*

8. **Gemma 4 has native JSON/function calling support.** Higher confidence for structured output than moondream or generic instruction-tuned models. *(Noted: May 2026.)*

---

# Chapter 8: Safety & Risk

> *This chapter must be substantially complete before any HIL or real flight testing begins.*

## Current Risk Level: **LOW** (SITL only, no real hardware)

A bug in the planner cannot crash a real airframe at this phase. Failure modes are constrained to:
- Wasted inference time
- Corrupt MAVLink commands rejected by SITL
- The Mission Manager process crashing

None of these have physical consequences. This is the right phase to take risks on planning logic — try things, break things, learn fast.

## Risk Register *(template, to be populated before HIL)*

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| *(empty — populate before HIL)* | | | |

## Pre-flight Checklist *(to be developed before real flight)*

Placeholder. Will include:
- VLM output validation (schema check, pixel range check)
- Geofence verification
- Comms check (MAVLink heartbeat, VLM HTTP latency)
- Battery check
- Abort criteria (what triggers automatic RTL)

## Failure Modes

*Placeholder — to be expanded before HIL.*

For now, the design fallback is universal: **all failures default to RTL.**
- VLM unreachable → RTL
- VLM returns invalid JSON → RTL
- VLM returns coordinates outside the map → RTL (clamp first, log, then reconsider)
- MAVLink heartbeat lost → ArduPilot's own failsafe (RTL or LOITER, autopilot-side)
- Battery low → ArduPilot failsafe (RTL or LAND)

The autopilot already has its own failsafe behaviour; the VLM layer's job is to fail closed and let the autopilot recover.

---

# Chapter 9: Open Questions & Research Directions

> *The things we don't know yet. As questions are answered, move them to Chapter 7 (Lessons Learned).*

1. **Can Gemma 4 E2B reliably output valid JSON with pixel coordinates?** Native JSON support gives confidence, but unproven on our task.
2. **Does visual context meaningfully improve mission decisions over text-only?** Core thesis — needs measurement. Same model, same mission, with and without the map image.
3. **Does state machine memory improve decision quality?** Hypothesis: yes. Unproven. May also confuse smaller models with too much context.
4. **What is the right event granularity for state machine triggers?** Every waypoint reached? Every mode change? Every N seconds with no event? We don't know yet.
5. **Can the model reason about mission patterns with accumulated context?** Or does it treat every prompt as fresh regardless?
6. **What does X-Plane integration unlock vs SITL?** Photorealistic input, moving camera, 3D world. Different problem, more interesting answers.
7. **What are the minimum safety requirements before real flight?** Chapter 8 needs to be substantially complete first.
8. **How does decision quality degrade under adversarial conditions?** Weather, sensor noise, comms latency, obscured map regions.
9. **Is there a meaningful difference between E2B and E4B for mission planning specifically?** Requires Orin NX hardware to test.

---

# Chapter 10: Session Log

> *Updated at the end of every session. Each entry summarizes what was built, what was learned, and what comes next.*

| Date | Session | What landed | What's Next |
|---|---|---|---|
| **2026-04-20** | 1 | Project setup. GitHub repo. `mission_manager/` skeleton. WSL2 environment. CLAUDE.md scaffolded. | Wire up MAVLink telemetry, build a real Planner/Executor, get a SITL aircraft to fly itself to a waypoint. |
| **2026-04-23** | 2 | TelemetryListener, Planner, Executor. First autonomous flight in SITL — armed, took off, hit a waypoint, RTL. | Replace the stub planner with an actual LLM. Get Ollama running on Penny Royal. |
| **2026-05-02** | 3 | LLM integration via Ollama. Stub planner replaced with real planner calling Llama 3.2. Arm/takeoff sequence shaken out. First text-only mission decisions. | Discover the coordinate-math limitation. Pivot to visual input — design the MapCompositor and the pixel-coordinate schema. |
| **2026-05-03** | 4 | MapCompositor. VLM architecture (pixel coordinates, image input). VILA wrapper sketched. The pivot from GPS prompts to visual prompts. | Make the backend layer pluggable. Do a hard code review pass. Try a real VLM (moondream) and see what breaks. |
| **2026-05-06** | 5 | Backend abstraction (`InferenceBackend` ABC). Code review pass — bug fixes across `main.py`, `executor.py`, `map_compositor.py`, `download_map.py`. Switched OllamaBackend to `/api/chat` for vision. Moondream tested, found wanting. JetPack upgrade. llama.cpp backend added. Gemma 4 E2B chosen. CLAUDE.md restructured with the inference backend history. MATT.md added and then restructured into chapter format. | Build llama.cpp natively with CUDA on Penny Royal. Download Gemma 4 E2B GGUF + mmproj. Run the first real vision inference against a map image. Populate Chapter 6 with the first mission result. |

---

*Last updated: end of Session 5, 2026-05-06.*
