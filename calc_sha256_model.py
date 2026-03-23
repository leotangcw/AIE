#!/usr/bin/env python3
import hashlib
import os

model_dir = "/mnt/d/models/Qwen3.5-35B-A3B"
output_file = "/mnt/d/deploy_knowledge/qwen35_35b_sha256_local.txt"

# 确保输出目录存在
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# 获取所有 model.safetensors-*.safetensors 文件
files = []
for f in os.listdir(model_dir):
    if f.startswith("model.safetensors-") and f.endswith(".safetensors"):
        files.append(f)

# 按文件名排序
files.sort()

print(f"找到 {len(files)} 个文件:")
for f in files:
    print(f"  - {f}")

print()

# 计算每个文件的 SHA256 并追加到输出文件，使用更大的块大小 (64MB)
with open(output_file, "a") as out:
    for filename in files:
        filepath = os.path.join(model_dir, filename)
        print(f"正在计算 {filename} 的 SHA256...")
        
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024 * 1024), b""):
                sha256_hash.update(chunk)
        
        checksum = sha256_hash.hexdigest()
        line = f"{checksum}  {filepath}\n"
        out.write(line)
        print(f"  {checksum}  {filepath}")

print()
print(f"所有校验和已追加保存到 {output_file}")
