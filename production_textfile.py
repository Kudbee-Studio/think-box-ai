#!/usr/bin/env python3
"""KUDBEE Production - Using textfile method (avoids escaping issues)"""
import subprocess
import os

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
scenes_dir = "/opt/kudbee/outputs/PROD-FINAL/scenes"
os.makedirs(scenes_dir, exist_ok=True)

scene_data = [
    (0, 5, "What if your ideas could build themselves?"),
    (5, 12, "KUDBEE - Think Box AI"),
    (12, 18, "Specialized agents that collaborate"),
    (18, 24, "Write. Code. Design. Analyze."),
    (24, 30, "Each one persistent. Each one purpose-built."),
    (30, 38, "They remember what they learn."),
    (38, 46, "One sentence in. Finished production out."),
    (46, 54, "3x NVIDIA L40S. 256GB RAM."),
    (54, 62, "GPT-OSS. ACE-Step. FLUX. LTX."),
    (62, 75, "KUDBEE. Think Box AI."),
    (75, 85, "kudbee.ai"),
    (85, 90, None),  # No text
]

generated = 0
for i, (start, end, text) in enumerate(scene_data):
    duration = end - start
    output = f"{scenes_dir}/scene_{i:02d}.mp4"
    
    if text:
        # Write text to file (avoids escaping issues)
        text_file = f"{scenes_dir}/text_{i:02d}.txt"
        with open(text_file, "w") as f:
            f.write(text)
        
        vf = f"drawtext=fontfile={FONT}:textfile={text_file}:fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:reload=1"
    else:
        vf = "format=yuv420p"
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0a0a2e:s=1920x1080:d={duration}:r=30",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if os.path.exists(output):
        generated += 1
        print(f"Scene {i:02d}: OK ({duration}s) - {text[:40] if text else 'blank'}")
    else:
        print(f"Scene {i:02d}: FAIL - {text[:40] if text else 'blank'}")
        lines = result.stderr.strip().split("\n")
        for line in lines[-2:]:
            print(f"  {line}")

print(f"\nTotal: {generated}/{len(scene_data)} scenes")

# Create concat file
with open(f"{scenes_dir}/concat.txt", "w") as f:
    for i in range(len(scene_data)):
        f.write(f"file 'scene_{i:02d}.mp4'\n")

# Assemble video
video = "/opt/kudbee/outputs/PROD-FINAL/video.mp4"
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", f"{scenes_dir}/concat.txt", "-c", "copy", video
], capture_output=True, timeout=60)

# Add narration + music
narration = "/opt/kudbee/outputs/PROD-20260830-170623/narration.wav"
music = "/opt/kudbee/outputs/midwest-hiphop-d3736a93.mp3"
final = "/opt/kudbee/outputs/PROD-FINAL/ku3bee-trailer-final.mp4"

if os.path.exists(video) and os.path.getsize(video) > 1000:
    if os.path.exists(narration) and os.path.exists(music):
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video,
            "-i", narration,
            "-i", music,
            "-filter_complex", "[1:a]volume=1.0[narr];[2:a]volume=0.25[musc];[narr][musc]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", final
        ], capture_output=True, timeout=60)
    
    if os.path.exists(final):
        subprocess.run(["cp", final, "/var/www/html/ku3bee-trailer-latest.mp4"])
        subprocess.run(["cp", final, "/opt/kudbee/outputs/ku3bee-trailer-latest.mp4"])
        size = os.path.getsize(final)
        print(f"\nFINAL VIDEO: {final}")
        print(f"Size: {size/1024/1024:.1f} MB")
        print(f"URL: http://87.58.149.157/ku3bee-trailer-latest.mp4")
    else:
        print("\nFinal assembly failed")
else:
    print("\nVideo assembly failed - not enough scenes")
