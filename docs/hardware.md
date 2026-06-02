# Hardware Reference — Pennyroyal (Jetson Orin Nano Super)

## Document Control
- Version: 0.2
- Status: Draft
- Last updated: 2026-06-01

## Memory Architecture

Pennyroyal has 7.6 GiB of unified LPDDR5 memory shared between CPU and GPU. There is no discrete VRAM. Every allocation — model weights, the CLIP vision tower, the KV cache, and per-request compute buffers — draws from the same physical pool.

A single image inference request with Q8_0 weights consumes approximately:

| Component | Size |
|---|---|
| Q8_0 model weights | ~4.7 GiB |
| CLIP vision projector | ~530 MiB |
| Compute buffer (per image request) | ~528 MiB |
| **Total** | **~5.8 GiB** |

This leaves roughly 1.8 GiB for OS, runtime, and other processes. The system runs stably across multiple sequential requests with `--cache-ram 0` to prevent unbounded cache growth. See [troubleshooting.md](troubleshooting.md) for crash diagnosis.

## Quantization

The `ggml-org/gemma-4-E2B-it-GGUF` HuggingFace repository publishes only two quantizations for the E2B model: `bf16` (9.3 GiB) and `Q8_0` (4.97 GiB). Q4_K_M does not exist for this model. If `llama-server` is invoked with a `:Q4_K_M` HuggingFace tag, the downloader silently falls back to Q8_0.

The project runs Q8_0 throughout. Q8_0 fits comfortably in the 7.6 GiB pool and has not been a bottleneck. Quantization is not a current concern.

## Model Files on Pennyroyal

Model files live in `~/models/`:

| File | Purpose |
|---|---|
| `gemma-4-E2B-it-Q8_0.gguf` | Model weights (4.7 GiB, Q8_0) |
| `mmproj-gemma-4-E2B-it-Q8_0.gguf` | CLIP vision projector (~530 MiB) |
