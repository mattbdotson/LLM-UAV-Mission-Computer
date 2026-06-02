# Troubleshooting

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-01

---

## llama-server crashes on Nth request with `cudaMalloc failed: out of memory`

**Symptom**: Server runs for 1–2 requests, then logs:

```
cudaMalloc failed: out of memory
CUDA error: out of memory
terminate called after throwing an instance of 'std::runtime_error'
```

**Root cause**: Prompt cache growth. Each request appended its prompt tokens to a persistent cache in GPU memory. After 2–3 requests the 528 MiB compute buffer could no longer be allocated.

**Fix**: Launch `llama-server` with `--cache-ram 0`. This disables the prompt cache entirely. See [inference_setup.md](inference_setup.md) for the full launch command.

---

## GPU memory does not fully recover after a crash

**Symptom**: After a server crash, restarting `llama-server` fails or produces degraded performance. Each crash leaks roughly 30–300 MiB of unified memory that is not returned to the pool until the host reboots.

**Fix**: `sudo reboot` on Pennyroyal. This is the only reliable recovery after repeated crashes. A single crash followed by a clean restart is usually recoverable without a reboot.

---

## `--image-min-tokens` / `--image-max-tokens` flags rejected at startup

**Symptom**: `llama-server` exits immediately with `error: unknown argument`.

**Cause**: The NVIDIA prebuilt Docker image (`ghcr.io/nvidia-ai-iot/llama_cpp:gemma4-jetson-orin`) predates these flags.

**Fix**: Either omit the flags (defaults work for this use case) or switch to the native llama.cpp build, which supports them. See [inference_setup.md](inference_setup.md).

---

## Gemma wraps JSON response in markdown code fences

**Symptom**: Mission manager logs a JSON parse error and falls back to RTL. The raw response in the log looks like:

```
```json
{"command": "goto_pixel", ...}
```
```

**Fix**: Already handled. `backends/llamacpp_backend.py` strips markdown fences via `re.search(r'\{.*\}', content, re.DOTALL)` before returning content to the planner. If a future model variant uses a different wrapper format, inspect that file.

---

## EventMonitor fires `no_progress` during normal transit

**Symptom**: Aircraft transitions to STUCK state while still climbing or flying a long leg, before reaching any ON_TASK waypoint.

**Root cause**: The original 60s threshold was shorter than the typical leg duration for long transits.

**Fix**: Threshold is now 180s in `core/event_monitor.py`. Additionally, `no_progress` only fires when altitude is above 50m (already airborne check). If missions use very long legs, increase `no_progress_timeout` further.

---

## Model reports visual features but reasoning appears fabricated

**Symptom**: Chain-of-thought includes phrases like `(Simulated based on the provided image)` or describes landmarks that are not present in the debug map.

**Context**: Gemma 4 E2B (2B parameters) will sometimes confabulate visual descriptions. The model's self-reported "visual" reasoning should be cross-checked against the debug maps saved per decision in `mission_manager/debug/maps/<run_id>/`.

**Mitigation**: Prompt design strips named landmarks and explicit coordinates to reduce the model's ability to solve phases by text arithmetic rather than vision. See [prompt_design.md](prompt_design.md).

---

## Wrong model quantization loaded (Q8_0 instead of Q4_K_M)

**Symptom**: Server starts but crashes after 1–2 image requests due to memory exhaustion, even with `--cache-ram 0`.

**Diagnosis**: Check startup logs for `print_info: file type`. If it shows `Q8_0`, the wrong file is loaded.

**Fix**: Confirm the model path points to `gemma-4-E2B-it-Q4_K_M.gguf`, not a Q8_0 variant. The NVIDIA Docker image silently ships Q8_0 regardless of the HuggingFace tag. See [hardware.md](hardware.md).
