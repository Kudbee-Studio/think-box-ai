cat > /opt/kudbee/record-production.sh << 'SCRIPT'
#!/bin/bash
# Record actual Think Box production activity
# Shows: GPU usage, files being generated, queue progress

DURATION="${1:-7200}"  # Default 2 hours
OUTPUT="/opt/kudbee/recordings/production-$(date +%Y%m%d-%H%M%S).mp4"
mkdir -p /opt/kudbee/recordings

echo "Recording production activity for ${DURATION}s..."

# Create a live dashboard showing actual work
python3 << "PYTHON" &
import time, subprocess, os
from datetime import datetime

start = time.time()
while time.time() - start < DURATION:
    os.system("clear")
    print("=" * 80)
    print(f"  KUDBEE Production Monitor — {datetime.now().strftime("%H:%M:%S")}")
    print("=" * 80)
    
    # GPU Status
    print("\n  GPU:")
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used", "--format=csv,noheader"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().split("\n"):
            print(f"    {line}")
    except:
        pass
    
    # Recent files
    print("\n  Recent Outputs:")
    try:
        r = subprocess.run(["ls", "-lt", "/opt/kudbee/outputs/"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().split("\n")[1:8]:
            if line.strip():
                print(f"    {line[:70]}")
    except:
        pass
    
    # Disk usage
    print("\n  Storage:")
    try:
        r = subprocess.run(["df", "-h", "/opt/kudbee/outputs/"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().split("\n"):
            print(f"    {line}")
    except:
        pass
    
    time.sleep(2)
PYTHON

PYTHON_PID=$!

# Record the dashboard
export DISPLAY=:99
Xvfb $DISPLAY -screen 0 1920x1080x24 -ac &
XVFB_PID=$!
sleep 2

ffmpeg -y -f x11grab -video_size 1920x1080 -i $DISPLAY -t $DURATION \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
    "$OUTPUT" 2>/dev/null

kill $PYTHON_PID 2>/dev/null
kill $XVFB_PID 2>/dev/null

echo "Recording complete: $OUTPUT"
ls -la "$OUTPUT"
SCRIPT
