#!/bin/bash
echo "=== Checking model directory ==="
ls -la /mnt/d/models/Qwen3.5-35B-A3B/ 2>&1

echo ""
echo "=== Counting safetensors files ==="
find /mnt/d/models/Qwen3.5-35B-A3B/ -name "*.safetensors" 2>/dev/null | wc -l

echo ""
echo "=== Listing safetensors files ==="
find /mnt/d/models/Qwen3.5-35B-A3B/ -name "*.safetensors" 2>/dev/null

echo ""
echo "=== Checking for temp directory ==="
ls -la /mnt/d/models/Qwen3.5-35B-A3B/._____temp/ 2>&1
