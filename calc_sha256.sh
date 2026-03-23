#!/bin/bash
MODEL_DIR="/mnt/d/models/Qwen/Qwen3.5-27B-FP8"
OUTPUT_FILE="/tmp/qwen35_sha256_local.txt"

# Find all model.safetensors files and calculate SHA256
find "$MODEL_DIR" -name "model.safetensors" -type f -exec sha256sum {} \; > "$OUTPUT_FILE" 2>&1

# Display results
cat "$OUTPUT_FILE"
