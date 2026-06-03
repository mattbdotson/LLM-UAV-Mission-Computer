# Troubleshooting

## Document Control
- Version: 0.2
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

**Root cause**: This was caused by the NVIDIA-prebuilt Docker image (`ghcr.io/nvidia-ai-iot/llama_cpp:gemma4-jetson-orin`), which has a memory management defect in its llama-server binary. The crash occurred reliably on the 3rd sequential multimodal call regardless of model size. Switching to a current native llama.cpp build on the same Q8_0 weights eliminated the crash across 6+ sequential calls.

`--cache-ram 0` is still required: without it, each request appends to a persistent prompt cache that grows unboundedly and will eventually exhaust the memory pool even on the native build. But `--cache-ram 0` alone does not fix the Docker binary.

**Fix**: Use the native llama.cpp build. See [inference_setup.md](inference_setup.md). The Docker path is no longer used.

---

## GPU memory does not fully recover after a crash

**Symptom**: After a server crash, restarting `llama-server` fails or produces degraded performance. Each crash leaks roughly 30–300 MiB of unified memory that is not returned to the pool until the host reboots.

**Fix**: `sudo reboot` on Pennyroyal. This is the only reliable recovery after repeated crashes. A single crash followed by a clean restart is usually recoverable without a reboot.

---

## `--image-min-tokens` / `--image-max-tokens` flags rejected at startup

**Symptom**: `llama-server` exits immediately with `error: unknown argument`.

**Cause**: The NVIDIA prebuilt Docker image predates these flags.

**Fix**: Switch to the native llama.cpp build, which supports them. See [inference_setup.md](inference_setup.md).

---

## Gemma wraps JSON response in markdown code fences

**Symptom**: Mission manager logs a JSON parse error and falls back to RTL. The raw response in the log looks like:

````
```json
{"command": "goto_pixel", ...}
```
````

**Fix**: Already handled. `backends/llamacpp_backend.py` strips fences via `re.search(r'\{.*\}', content, re.DOTALL)` before returning content to the planner. If a future model variant uses a different wrapper format, inspect that file.

---

## EventMonitor fires `no_progress` during a legitimate long-leg transit

**Symptom**: Aircraft transitions to STUCK state mid-flight on a long leg, before the waypoint is reached.

**Root cause**: The elapsed-time threshold is shorter than the leg duration. A full-map north-south leg takes longer than 180s at cruise speed; the timer fires as a false positive.

**Current workaround**: Threshold is 600s in `core/event_monitor.py`. This covers full-map legs at typical cruise speeds.

**Deferred proper fix**: Replace the elapsed-time check with a progress-toward-target check — monitor distance-to-waypoint closing rate and fire `no_progress` only when groundspeed is healthy but distance is not decreasing. This avoids any fixed-time sensitivity to leg length. That refactor is deferred.

---

## Model reports visual features but reasoning appears fabricated

**Symptom**: Chain-of-thought includes phrases like `(Simulated based on the provided image)` or describes landmarks inconsistent with the debug map.

**Context**: Gemma 4 E2B (2B parameters) will sometimes confabulate visual descriptions. Cross-check self-reported reasoning against debug maps saved per decision in `mission_manager/debug/maps/<run_id>/`.

**Mitigation**: Prompt design strips named landmarks and explicit coordinates to reduce the model's ability to solve phases by text arithmetic. See [prompt_design.md](prompt_design.md).

---

## Model writes empty or contradictory scratchpad notes

**Symptom**: `decisions.jsonl` shows `progress` or `next_intent` as null across multiple decisions, or the notes contradict the aircraft's actual position visible in the debug maps.

**Context**: This is expected behaviour. The system does not filter, validate, or correct the scratchpad — it stores and surfaces whatever the model writes, verbatim. A 2B edge model will sometimes write empty notes, repeat previous notes unchanged, or describe a phase that doesn't match its current map position. These are all observable in the `decisions.jsonl` log alongside the corresponding debug map images.

**What to do**: Treat contradictory notes as a data point, not a bug. Cross-reference each decision's `progress` / `next_intent` text against the corresponding debug map (saved in `debug/maps/<run_id>/`) to characterise how often the model's self-reported state is accurate. This is the measurement the scratchpad mechanism is designed to support. See [scratchpad.md](scratchpad.md) for design intent.

---

## Model regresses to Phase 1 after `no_progress` / STUCK fires

**Symptom**: After the `stuck` prompt fires, the model issues a Phase 1 waypoint even though earlier phases are complete. Progress is lost.

**Root cause**: The model has no persistent memory of completed phases. On re-prompt it reads the mission objective from scratch, identifies the first instruction, and restarts. This was observed concretely in run `20260601_232846`: stuck fired during a legitimate Phase 4 transit at (314, 263), and the model responded with a Phase 1 waypoint at (512, 263).

**Current state**: No fix implemented. This is the experimental motivation for the phase-state-injection A/B test described in the scoring spec (§1.2). See [results.md](results.md) for the full run record.
