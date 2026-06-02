# Hardware Reference — Pennyroyal (Jetson Orin Nano Super)

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-01

## Memory Architecture

Pennyroyal has 7.6 GiB of unified LPDDR5 memory shared between CPU and GPU. There is no discrete VRAM. Every allocation — model weights, the CLIP vision tower, the KV cache, and per-request compute buffers — draws from the same physical pool.

Practical headroom is tight. A single image inference request with Q8_0 weights consumes approximately:

| Component | Size |
|---|---|
| Q8_0 model weights | ~4.7 GiB |
| CLIP vision projector | ~530 MiB |
| Compute buffer (per image request) | ~528 MiB |
| **Total** | **~5.8 GiB** |

This leaves roughly 1.8 GiB for OS, runtime, and other processes — enough for a single request but insufficient for a growing prompt cache.

## Quantization

Q4_K_M weights (~2.3 GiB) are strongly preferred over Q8_0. The reduction frees approximately 2.4 GiB, giving the compute buffer and KV cache room to operate without exhausting the pool across multiple requests.

**Important**: the NVIDIA-prebuilt llama_cpp Docker image (`ghcr.io/nvidia-ai-iot/llama_cpp:gemma4-jetson-orin`) ships Q8_0 weights regardless of the `:Q4_K_M` HuggingFace tag passed to `llama-server`. Always confirm the loaded quantization by inspecting the `print_info: file type` line in startup logs before running a mission.

## Model Files on Pennyroyal

Model files live in `~/models/`:

| File | Purpose |
|---|---|
| `gemma-4-E2B-it-Q4_K_M.gguf` | Model weights (Q4_K_M quantization) |
| `mmproj-gemma-4-E2B-it-Q8_0.gguf` | CLIP vision projector |
