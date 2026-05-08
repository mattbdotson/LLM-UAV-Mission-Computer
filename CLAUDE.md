# LLM-UAV Mission Computer

## Project Overview
Autonomous UAV mission management system that uses a Vision Language Model (VLM) as the autonomy layer. The VLM receives top-down map images showing the aircraft's current position and makes high-level mission decisions expressed as pixel coordinates on the map. The autopilot handles all low-level flight control — the VLM only handles mission-level reasoning.

The core research question is: **what can a small edge VLM do as an autonomous mission planner when given visual spatial context?**

## Hardware
- **Dev PC**: Windows machine running WSL2 (Ubuntu 22.04)
- **Mission Computer**: NVIDIA Jetson Orin Nano Super Developer Kit, nicknamed "Penny Royal" (Neal Asher Polity universe reference)
  - JetPack 6.2.2, L4T 36.5 (upgraded from 36.4.7)
  - 8GB unified memory
  - 64GB microSD (NVMe SSD arriving — Crucial P3 500GB, will enable faster Docker pulls and potentially larger models via TensorRT in future)
  - IP: 192.168.1.177
  - Username: matthew
- **Autopilot**: Virtualized via ArduPlane SITL (upgrade path to real hardware planned)

## Architecture
Dev PC (WSL2)                          Penny Royal (Jetson Orin Nano)
─────────────────────                  ──────────────────────────────
JSBSim (flight physics)                VLM Inference Server
↕                                (llama.cpp + Gemma 4 E2B)
ArduPlane SITL        ←── MAVLink ──►       ↕ HTTP
(full autopilot                        Mission Manager
firmware as process)                  ├── Telemetry Listener
├── Planner (calls VLM)
└── Executor (MAVLink cmds)

### Key Design Decisions
- **LLM at mission layer only** — autopilot retains full control loop authority. VLM only issues high-level waypoint/mode commands via MAVLink
- **Visual input** — VLM receives a 384×384px top-down map image with aircraft position, heading arrow, flight trail, and mission target overlaid on OpenStreetMap tiles
- **Pixel coordinate output** — VLM outputs pixel coordinates (x, y) on the map rather than GPS coordinates. The executor converts pixels to GPS using known map bounds. This avoids asking the LLM to do coordinate math it can't do reliably.
- **Pluggable backends** — inference backend is swappable via `.env` (Ollama, VILA, TensorRT, llama.cpp)
- **Structured JSON output** — VLM must output a JSON command with a reasoning field for traceability
- **RTL fallback** — any parse error or backend failure defaults to Return To Launch

### State Machine
States: PREFLIGHT → TAKEOFF → TRANSIT → ON_TASK ↔ STUCK → RETURNING → LANDED

## Project Structure
LLM-UAV-Mission-Computer/
├── CLAUDE.md                          # this file
├── mission_manager/
│   ├── main.py                        # entry point, starts SITL, runs planning loop
│   ├── requirements.txt
│   ├── core/
│   │   ├── telemetry.py               # MAVLink state listener
│   │   ├── planner.py                 # decision logic, calls backend
│   │   └── executor.py                # translates commands to MAVLink
│   ├── backends/
│   │   ├── base.py                    # abstract interface all backends implement
│   │   ├── __init__.py                # load_backend() factory function
│   │   ├── ollama_backend.py          # Ollama (vision via /api/chat)
│   │   ├── llamacpp_backend.py        # llama.cpp server (OpenAI-compatible API)
│   │   ├── vila_backend.py            # nano_llm VILA server (vision + text)
│   │   └── tensorrt_backend.py        # TensorRT placeholder (future)
│   ├── mapping/
│   │   ├── map_compositor.py          # draws aircraft/trail/target on map tile
│   │   └── download_map.py            # downloads OpenStreetMap tiles
│   ├── config/
│   │   ├── .env                       # backend selection, hosts, ports
│   │   ├── .env.example               # template with all keys
│   │   └── map_config.py              # map bounds, mission target coords
│   ├── prompts/
│   │   ├── system_prompt.txt          # mission objective and command schema
│   │   └── user_prompt.txt            # per-cycle state template
│   ├── servers/
│   │   └── vila_server.py             # Flask HTTP wrapper for nano_llm VILA
│   ├── scripts/
│   │   └── start_inference_server.sh  # launches llama-server on Penny Royal
│   ├── tests/
│   │   ├── test_vlm.py                # Ollama VLM integration test (health, text, image)
│   │   └── test_vila.py               # VILA integration test (health, text, image)
│   └── assets/
│       └── map_tile.png               # OSM tile of Canberra SITL area (8km x 8km)

## Command Schema
The VLM outputs one of these JSON commands each planning cycle:

```json
{"command": "goto_pixel", "reasoning": "...", "params": {"x": 200, "y": 200}}
{"command": "loiter", "reasoning": "...", "params": {"x": 200, "y": 200, "radius": 500, "alt": 150}}
{"command": "goto_waypoint", "reasoning": "...", "params": {"lat": -35.36, "lon": 149.16, "alt": 100}}
{"command": "rtl", "reasoning": "...", "params": {}}
```

The `reasoning` field is logged for every decision — this is critical for understanding and debugging VLM behavior.

## Backend Configuration (.env)
INFERENCE_BACKEND=llamacpp    # ollama | vila | tensorrt | llamacpp
OLLAMA_HOST=192.168.1.177
OLLAMA_PORT=11434
OLLAMA_MODEL=moondream
VILA_HOST=192.168.1.177
VILA_PORT=5000
TENSORRT_HOST=192.168.1.177
TENSORRT_PORT=8000
TENSORRT_MODEL=vila
LLAMACPP_HOST=192.168.1.177
LLAMACPP_PORT=8080

## Map System
- Base tile: OpenStreetMap, 8km × 8km centered on SITL default location (Canberra, Australia)
- Tile size: 2304×2304px, resized to 512×512 for VLM input
- Map bounds: lat -35.407 to -35.326, lon 149.117 to 149.216
- SITL default position: lat -35.3632, lon 149.1652 (Jerrabomberra area, Canberra)
- Mission target: lat -35.363261, lon 149.165230 (near highway junction)
- Aircraft drawn as blue arrow showing heading, trail as blue line, target as red crosshair

## Simulation Stack
- **JSBSim**: flight dynamics model (fixed-wing physics)
- **ArduPlane SITL**: full ArduPilot firmware compiled as Linux binary
- **MAVProxy**: ground control station, exposes MAVLink on UDP port 14552
- SITL launches automatically from `main.py` via subprocess
- SITL default location: Canberra, Australia (-35.3632, 149.1652), elevation 584m

## MAVLink Interface
- SITL → Mission Manager: UDP port 14552
- Mission Manager uses pymavlink for all autopilot communication
- Autopilot modes used: GUIDED (waypoint commands), TAKEOFF, LOITER, RTL
- After any LOITER command, executor switches back to GUIDED before next waypoint
- Arm sequence: set GUIDED → arm with force flag 21196 → TAKEOFF mode → back to GUIDED

## Inference Backend History
- **Ollama** was tried first but cannot properly use the Jetson GPU on Orin Nano due to memory allocator issues with the unified memory architecture. All inference fell back to CPU and timed out.
- **Models attempted via Ollama**: llama3.2:1b, llama3.2:3b, moondream, qwen2.5vl:3b, gemma4:e2b, gemma4:e4b — none ran successfully on GPU.
- **JetPack upgrade**: 36.4.7 → 36.5 (JetPack 6.2.2) fixed the CUDA memory allocation bug, but Ollama still cannot use the GPU.
- **llama.cpp built natively with `DGGML_CUDA=ON`** is the correct path — it bypasses Ollama's broken memory management and talks directly to the GPU via CUDA kernels.
- **Gemma 4 E2B** is the largest model that fits on Orin Nano (E4B does not fit).
- **llama-server** exposes an OpenAI-compatible API on port 8080.
- The **vision projector** (mmproj file) must be loaded alongside the model for image input to work.

## Known Issues
- nano_llm/VILA deployment abandoned — replaced by llama.cpp + Gemma 4 E2B
- Text-only Ollama testing showed LLM struggles with coordinate math (expected)
- VLM pixel output approach designed specifically to avoid coordinate math

## What We Learned From Text-Only Testing
Running Llama 3.2 1B/3B against orbit and figure-8 missions revealed:
- LLMs understand mission intent well (issued RTL at mission completion unprompted)
- LLMs cannot reliably do coordinate geometry
- LLMs keep sending aircraft to current position as waypoint (no offset calculation)
- The pixel coordinate approach directly addresses this limitation
- Reasoning field is valuable for debugging — shows what the model was thinking

## Current Status
- ✅ llama.cpp native CUDA build running on Penny Royal (Jetson Orin Nano Super 8GB)
- ✅ Gemma 4 E2B with vision projector deployed and serving on port 8080
- ✅ Event-driven state machine architecture implemented and tested
- ✅ Mission 001 completed (highway junction, partial success)
- ✅ Mission 002 completed (boundary pattern, full success — perfect 4/4 decisions)
- ✅ Event-driven planning loop working correctly (LLM called only at decision points)
- ✅ Debug map images saved per run in `mission_manager/debug/maps/<run_id>/`

## Proven Capabilities
- Gemma 4 E2B correctly understands the pixel coordinate system (x=0 west, y=0 north)
- Multi-phase conditional mission logic works reliably
- State machine fires LLM only at decision points (not time-driven)
- Mission context memory correctly accumulates across decisions
- Image is being sent and received correctly by llama-server

## Upgrade Path
1. ✅ SITL + mission manager pipeline
2. ✅ Pluggable backend abstraction
3. ✅ Map compositor + pixel command schema
4. ❌ Deploy VILA on Jetson — abandoned, replaced by llama.cpp + Gemma 4 E2B
5. ✅ Build llama.cpp with CUDA on Penny Royal
6. ✅ Download Gemma 4 E2B GGUF and vision projector
7. ✅ Test Gemma 4 E2B vision inference with map image
8. ✅ First VLM vision mission test (Mission 001 — highway junction)
9. ✅ Event-driven state machine + mission context memory
10. ✅ Boundary pattern mission (Mission 002 — full success)
11. ⬜ Visual landmark identification mission (racecourse, highway junction)
12. ⬜ More complex patterns (figure-8, expanding square)
13. ⬜ Simulated anomaly detection (off-course, wind correction)
14. ⬜ TensorRT backend implementation
15. ⬜ Real autopilot hardware (HIL upgrade)

## Development Commands
```bash
# Start mission manager (also starts SITL)
cd ~/LLM-UAV-Mission-Computer/mission_manager
python3 main.py

# Download/refresh map tiles
python3 mapping/download_map.py

# Test VLM integration (Ollama-based)
python3 tests/test_vlm.py

# Test VILA integration
python3 tests/test_vila.py

# Start llama-server on Penny Royal
bash scripts/start_inference_server.sh

# Switch backend (edit config/.env)
INFERENCE_BACKEND=llamacpp  # llama.cpp native (recommended)
INFERENCE_BACKEND=ollama    # Ollama (CPU only on Jetson)
INFERENCE_BACKEND=vila      # VILA via nano_llm (abandoned)

# SSH into Penny Royal
ssh matthew@192.168.1.177

# Shutdown Penny Royal safely
sudo shutdown -h now
```

## GitHub
Repository: https://github.com/mattbdotson/LLM-UAV-Mission-Computer
License: MIT
