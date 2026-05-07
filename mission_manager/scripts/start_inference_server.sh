#!/bin/bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/gemma-4-E2B-it-Q4_K_M.gguf \
  --mmproj ~/models/mmproj-gemma4-e2b-BF16.gguf \
  -ngl 99 \
  --flash-attn on \
  --host 0.0.0.0 \
  --port 8080 \
  -c 2048 \
  --image-min-tokens 70 \
  --image-max-tokens 70
