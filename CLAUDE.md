# LLM-UAV Mission Computer

## Project Overview
Autonomous UAV mission management system using a VLM (Vision Language Model) running on a Jetson Orin Nano as the autonomy layer. The VLM receives top-down map images showing aircraft position and makes mission decisions expressed as pixel coordinates on the map.

## Architecture
- SITL (ArduPlane + JSBSim) runs on dev PC via WSL2
- Mission Manager runs on dev PC, connects to SITL via MAVLink UDP
- VLM inference runs on Jetson Orin Nano (Penny Royal)
- VLM backend is pluggable: Ollama, VILA, or TensorRT

## Key Files
- `mission_manager/main.py` — entry point
- `mission_manager/core/` — telemetry, planner, executor
- `mission_manager/backends/` — pluggable inference backends
- `mission_manager/mapping/` — map compositor and tile downloader
- `mission_manager/prompts/` — system and user prompts (edit these to change mission)
- `mission_manager/servers/vila_server.py` — VILA HTTP wrapper for Jetson

## Current Status
- SITL + mission manager pipeline working
- Pluggable backend abstraction implemented
- Map compositor generating 384x384 images for VLM input
- Jetson awaiting NVMe SSD before VILA can be deployed
- Ollama backend available for text-only testing in the meantime

## Commands
- Start SITL + mission manager: `python3 mission_manager/main.py`
- Download map tiles: `python3 mission_manager/mapping/download_map.py`
- Test VILA integration: `python3 mission_manager/tests/test_vila.py`
