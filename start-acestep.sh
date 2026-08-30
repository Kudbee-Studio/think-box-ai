#!/bin/bash
# ACE-Step Music Generation Launcher
# Run on GPU server

set -e

echo "=== ACE-Step Music Generation Setup ==="

cd /opt/kudbee/ACE-Step

# Fix environment
export CUDA_VISIBLE_DEVICES=0
export PYTHONDONTWRITEBYTECODE=1

# Test the pipeline
python3 << 'PYTHON'
import sys
import os
import torch

print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPUs: {torch.cuda.device_count()}")

# Import ACE-Step
sys.path.insert(0, "/opt/kudbee/ACE-Step")
os.chdir("/opt/kudbee/ACE-Step")

try:
    from acestep.pipeline_ace_step import ACEStepPipeline
    print("✓ Pipeline imported")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Initialize pipeline
checkpoint_path = "/opt/kudbee/models/acestep"
print(f"Loading model from {checkpoint_path}...")

try:
    pipe = ACEStepPipeline(checkpoint_path=checkpoint_path)
    print("✓ Pipeline ready!")
except Exception as e:
    print(f"✗ Pipeline init failed: {e}")
    sys.exit(1)

print("\n=== ACE-Step Ready for Music Generation ===")
print(f"Model: ACE-Step 1.5 XL")
print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.1f} GB allocated")
print(f"Output: /opt/kudbee/outputs/")

# Keep alive
import time
while True:
    time.sleep(60)
PYTHON
