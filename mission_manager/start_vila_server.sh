#!/bin/bash
jetson-containers run \
  --name vila_server \
  --restart unless-stopped \
  -v ~/LLM-UAV-Mission-Computer/mission_manager:/mission_manager \
  dustynv/nano_llm:r36.4.0 \
  bash -c "pip install flask && python3 /mission_manager/vila_server.py"