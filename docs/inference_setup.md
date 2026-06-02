# Inference Stack Setup — Native llama.cpp on Pennyroyal

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-01

## Background

The mission manager originally used NVIDIA's prebuilt Docker image (`ghcr.io/nvidia-ai-iot/llama_cpp:gemma4-jetson-orin`). This was replaced by a native llama.cpp build on the Jetson host for the following reasons:

- The Docker image ships Q8_0 weights regardless of the quantization tag requested, exhausting the memory budget (see [hardware.md](hardware.md)).
- The Docker image predates several useful flags (`--image-min-tokens`, `--image-max-tokens`, `--cache-ram`) — the binary rejects them.
- A native build compiled with `DCMAKE_CUDA_ARCHITECTURES=87` targets the Orin's actual compute capability, avoiding a slow multi-arch compilation and producing a smaller binary.

NVIDIA's own Jetson AI Lab documentation recommends llama.cpp for Gemma 4 on Orin Nano. TensorRT-LLM has a Jetson branch but Gemma 4 multimodal support is immature; setup is weeks of integration work and not appropriate for this testbed.

## Build Instructions

Run on Pennyroyal:

```bash
sudo apt install -y build-essential cmake git
cd ~ && git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j$(nproc)
```

`DCMAKE_CUDA_ARCHITECTURES=87` corresponds to compute capability 8.7 (Ampere, Jetson Orin). Pinning this avoids building for all architectures and speeds up compilation.

## Launch Command

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma-4-E2B-it-Q4_K_M.gguf \
  --mmproj ~/models/mmproj-gemma-4-E2B-it-Q8_0.gguf \
  -ngl 99 --flash-attn on \
  --host 0.0.0.0 --port 8080 \
  -c 4096 --parallel 1 --cache-ram 0
```

## Flag Rationale

| Flag | Reason |
|---|---|
| `-ngl 99` | Offloads all layers to GPU. Without this, inference falls back to CPU and times out. |
| `--flash-attn on` | Reduces KV cache memory footprint and improves attention throughput. |
| `--parallel 1` | Reserves the slot pool for a single sequential workload. The mission manager calls the backend one request at a time. |
| `--cache-ram 0` | Disables prompt cache. Without this, each request appends to a persistent cache that grows unboundedly. On Pennyroyal's tight memory budget, this causes compute-buffer allocation failures within 2–3 requests and crashes the server. See [troubleshooting.md](troubleshooting.md). |

## Verifying GPU Inference

Check the startup log for:

```
ggml_cuda_init: GGML_CUDA_FORCE_MMQ = 0
ggml_cuda_init: CUDA_USE_TENSOR_CORES = 1
```

And confirm model quantization:

```
print_info: file type = Q4_K - Medium
```

If `file type` shows `Q8_0`, the wrong model file is loaded — stop the server, confirm the path, and restart.
