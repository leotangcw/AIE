#!/usr/bin/env python3
import hashlib
import glob
import os

model_dir = "/mnt/d/models/Qwen/Qwen3.5-27B-FP8"
output_file = "/tmp/qwen35_md5_local.txt"

# Find all matching files
pattern = os.path.join(model_dir, "model.safetensors-*.safetensors")
files = sorted(glob.glob(pattern))

if not files:
    print(f"No files found matching pattern: {pattern}")
    # Try to list the directory
    try:
        entries = os.listdir(model_dir)
        print(f"Directory contents: {entries[:20]}")
    except Exception as e:
        print(f"Error listing directory: {e}")
else:
    results = []
    for filepath in files:
        try:
            md5_hash = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5_hash.update(chunk)
            results.append(f"{md5_hash.hexdigest()}  {filepath}")
            print(f"Processed: {filepath}")
        except Exception as e:
            results.append(f"ERROR: {filepath} - {e}")
            print(f"Error processing {filepath}: {e}")
    
    # Write results
    with open(output_file, "w") as f:
        f.write("\n".join(results) + "\n")
    
    print(f"\nResults written to {output_file}")
    print(f"Total files processed: {len(files)}")
