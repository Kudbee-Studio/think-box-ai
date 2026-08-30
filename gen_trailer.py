#!/usr/bin/env python3
"""Generate KUDBEE 90-second trailer with FFmpeg"""
import subprocess
import os

scenes = [
    {"text": "What if your ideas\ncould build themselves?", "duration": 4, "color": "0a0a2e", "fontsize": 48},
    {"text": "KUDBEE\nThink Box AI", "duration": 6, "color": "0a0a2e", "fontsize": 100},
    {"text": "Specialized agents\nthat collaborate", "duration": 6, "color": "0a0a2e", "fontsize": 42},
    {"text": "Write\nCode\nDesign\nAnalyze", "duration": 6, "color": "0a0a2e", "fontsize": 48},
    {"text": "Each one persistent\nEach one purpose-built", "duration": 6, "color": "0a0a2e", "fontsize": 40},
    {"text": "They remember\nwhat they learn", "duration": 8, "color": "0a0a2e", "fontsize": 42},
    {"text": "One sentence in\nFinished production out", "duration": 8, "color": "0a0a2e", "fontsize": 48},
    {"text": "3x NVIDIA L40S\n256GB RAM\n1.3TB Storage", "duration": 8, "color": "0a0a2e", "fontsize": 32},
    {"text": "GPT-OSS\nACE-Step\nFLUX\nLTX", "duration": 8, "color": "0a0a2e", "fontsize": 40},
    {"text": "KUDBEE\nThink Box AI", "duration": 10, "color": "0a0a2e", "fontsize": 80},
    {"text": "kudbee.ai", "duration": 5, "color": "0a0a2e", "fontsize": 48},
]

os.makedirs("/tmp/trailer_scenes", exist_ok=True)

for i, scene in enumerate(scenes, 1):
    output = f"/tmp/trailer_scenes/scene_{i:02d}.mp4"
    # Escape newlines for ffmpeg
    text = scene["text"].replace("\n", "\\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={scene['color']}:s=1920x1080:d={scene['duration']}:r=30",
        "-vf", f"drawtext=text='{text}':fontsize={scene['fontsize']}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:fade=t=in:st=0:d=0.5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if os.path.exists(output):
        print(f"Scene {i:02d}: {scene['duration']}s - OK")
    else:
        print(f"Scene {i:02d}: FAILED - {result.stderr[:100]}")

# Create concat file
with open("/tmp/trailer_scenes/concat.txt", "w") as f:
    for i in range(1, len(scenes) + 1):
        f.write(f"file 'scene_{i:02d}.mp4'\n")

# Concatenate
print("\nAssembling video...")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", "/tmp/trailer_scenes/concat.txt",
    "-c", "copy",
    "/tmp/trailer_video.mp4"
], capture_output=True, timeout=60)

# Add narration
print("Adding narration...")
subprocess.run([
    "ffmpeg", "-y",
    "-i", "/tmp/trailer_video.mp4",
    "-i", "/tmp/narration_full.wav",
    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
    "-shortest",
    "/tmp/video_narration.mp4"
], capture_output=True, timeout=60)

# Add music
print("Adding music...")
subprocess.run([
    "ffmpeg", "-y",
    "-i", "/tmp/video_narration.mp4",
    "-i", "/tmp/trailer_music.wav",
    "-filter_complex", "[0:a]volume=1.0[narr];[1:a]volume=0.25[musc];[narr][musc]amix=inputs=2:duration=first[aout]",
    "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
    "/opt/kudbee/outputs/ku3bee-trailer-v1.mp4"
], capture_output=True, timeout=60)

if os.path.exists("/opt/kudbee/outputs/ku3bee-trailer-v1.mp4"):
    size = os.path.getsize("/opt/kudbee/outputs/ku3bee-trailer-v1.mp4")
    print(f"\nTRAILER COMPLETE: {size/1024/1024:.1f} MB")
else:
    print("\nTrailer assembly failed")
