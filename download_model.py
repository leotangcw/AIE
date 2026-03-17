#!/usr/bin/env python3
import subprocess
import os
import shutil

local_dir = "/mnt/d/models/Qwen3.5-35B-A3B"
cache_dir = "/mnt/d/models/.cache"

# 创建目录
os.makedirs(local_dir, exist_ok=True)
os.makedirs(cache_dir, exist_ok=True)

# 执行下载命令
cmd = ["modelscope", "download", "Qwen/Qwen3.5-35B-A3B", "--local_dir", local_dir, "--cache_dir", cache_dir]
print(f"执行命令: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=False)
print(f"返回码: {result.returncode}")
