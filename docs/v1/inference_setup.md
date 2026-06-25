# Inference Stack Setup — Native llama.cpp on Pennyroyal

## Document Control
- Version: 0.2
- Status: Draft
- Last updated: 2026-06-01

## Background

The mission manager originally used NVIDIA's prebuilt Docker image (`ghcr.io/nvidia-ai-iot/llama_cpp:gemma4-jetson-orin`). This image has two problems that make it unsuitable for this project:

1. **Outdated binary**: the image's llama-server build predates several flags (`--image-min-tokens`, `--image-max-tokens`) and may predate full `--cache-ram 0` support. The binary rejects unrecognised flags at startup.
2. **Memory stability bug**: the Docker image crashed reliably on the 3rd sequential multimodal request. A native build on the same Q8_0 weights, same context size, and same `--cache-ram 0` flag ran 6+ sequential calls without a crash. The Docker binary appears to have a memory management defect unrelated to model size.

The fix was switching to a native build. Model size (Q8_0) was not the issue and was not changed.

NVIDIA's own Jetson AI Lab documentation recommends llama.cpp for Gemma 4 on Orin Nano. TensorRT-LLM has a Jetson branch but Gemma 4 multimodal support is immature; setup is weeks of integration work and not appropriate for this testbed.

## Validated Build

The stable baseline is commit `354ebac8c` (llama.cpp version 9468), built with CUDA 12.6 on Pennyroyal. The build lives at `~/llama.cpp/`.

## Build Instructions

Run on Pennyroyal:

```bash
sudo apt install -y build-essential cmake git
cd ~ && git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j$(nproc)
```

`-DCMAKE_CUDA_ARCHITECTURES=87` targets compute capability 8.7 (Ampere, Jetson Orin). Pinning this avoids building for all architectures and speeds up compilation significantly.

## Launch Command

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma-4-E2B-it-Q8_0.gguf \
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
| `--cache-ram 0` | Disables prompt cache. Without this, each request appends to a persistent cache that grows unboundedly, eventually causing compute-buffer allocation failures. See [troubleshooting.md](troubleshooting.md). |

## Verifying GPU Inference

Check the startup log for CUDA initialisation:

```
ggml_cuda_init: GGML_CUDA_FORCE_MMQ = 0
ggml_cuda_init: CUDA_USE_TENSOR_CORES = 1
```

And confirm model file and quantization:

```
print_info: file type = Q8_0
print_info: file size = 4.61 GiB
```

This is the expected output. Q8_0 is the only quantization available for Gemma 4 E2B and is the correct file to load.
