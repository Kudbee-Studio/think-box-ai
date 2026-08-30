#!/usr/bin/env python3
import subprocess
import os

font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
scenes_dir = "/tmp/debug_scenes"
os.makedirs(scenes_dir, exist_ok=True)

scene_data = [
    (0, 5, "What if your ideas\ncould build themselves?"),
    (5, 12, "KUDBEE\nThink Box AI"),
    (12, 18, "Specialized agents\nthat collaborate"),
]

for i, (start, end, text) in enumerate(scene_data):
    duration = end - start
    output = f"{scenes_dir}/scene_{i:02d}.mp4"
    
    # Escape for FFmpeg: backslashes first, then newlines
    escaped = text.replace("\\", "\\\\").replace("\n", "\\n").replace(":", "\\:").replace("'", "")
    
    vf = f"drawtext=fontfile={font}:text={escaped}:fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0a0a2e:s=1920x1080:d={duration}:r=30",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        output
    ]
    
    print(f"Scene {i}: text={repr(text)}, escaped={repr(escaped)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if os.path.exists(output):
        print(f"  -> SUCCESS ({os.path.getsize(output)} bytes)")
    else:
        print(f"  -> FAILED (rc={result.returncode})")
        print(f"     stderr: {result.stderr[:300]}")
