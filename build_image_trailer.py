#!/usr/bin/env python3
"""Build trailer with AI-generated images + Ken Burns effect"""
import subprocess
import os

OUTPUT_DIR = "/opt/kudbee/outputs/PROD-IMAGE"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SCENES = [
    (0, 8, "scene_01_tower.png", "What if your ideas\ncould build themselves?"),
    (8, 16, "scene_02_agents.png", "KUDBEE\nThink Box AI"),
    (16, 24, "scene_03_developer.png", "Specialized agents\nthat collaborate"),
    (24, 32, "scene_04_title.png", "Write. Code.\nDesign. Analyze."),
    (32, 40, "scene_05_gpu.png", "3x NVIDIA L40S\n256 GB RAM"),
    (40, 48, "scene_01_tower.png", "Each one persistent\nEach one purpose-built"),
    (48, 56, "scene_02_agents.png", "They remember\nwhat they learn"),
    (56, 64, "scene_04_title.png", "One sentence in\nFinished production out"),
    (64, 72, "scene_05_gpu.png", "GPT-OSS • ACE-Step\nFLUX • LTX"),
    (72, 80, "scene_04_title.png", "KUDBEE\nThink Box AI"),
]

for i, (start, end, image, text) in enumerate(SCENES):
    duration = end - start
    output = f"{OUTPUT_DIR}/scene_{i:02d}.mp4"
    
    # Ken Burns zoom effect on image + text overlay
    escaped_text = text.replace("\n", "\\n").replace(":", "\\:")
    
    vf = (
        f"zoompan=z='1.0+0.02*in/100':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s=1920x1080:fps=30,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{escaped_text}':"
        f"fontsize=56:fontcolor=white:shadowcolor=black:shadowx=3:shadowy=3:"
        f"x=(w-text_w)/2:y=h-th-50:fade=t=in:st=0:d=0.5"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", f"/var/www/html/images/{image}",
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if os.path.exists(output):
        print(f"Scene {i:02d}: OK ({duration}s) - {image}")
    else:
        print(f"Scene {i:02d}: FAILED - {result.stderr[:80]}")

# Create concat file
with open(f"{OUTPUT_DIR}/concat.txt", "w") as f:
    for i in range(len(SCENES)):
        f.write(f"file 'scene_{i:02d}.mp4'\n")

# Assemble video
video_output = f"{OUTPUT_DIR}/video.mp4"
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", f"{OUTPUT_DIR}/concat.txt", "-c", "copy", video_output
], capture_output=True, timeout=60)

# Add narration and music
narration = "/opt/kudbee/outputs/PROD-FINAL/narration_gtts.mp3"
music = "/opt/kudbee/outputs/midwest-hiphop-d3736a93.mp3"
final = "/opt/kudbee/outputs/PROD-IMAGE/ku3bee-trailer-v5.mp4"

if os.path.exists(video_output):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_output,
        "-i", narration,
        "-i", music,
        "-filter_complex", "[1:a]volume=1.0,aresample=44100[narr];[2:a]volume=0.15,aresample=44100[musc];[narr][musc]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", final
    ], capture_output=True, timeout=60)
    
    if os.path.exists(final):
        # Deploy
        subprocess.run(["cp", final, "/var/www/html/ku3bee-trailer-latest.mp4"])
        subprocess.run(["cp", final, "/opt/kudbee/outputs/ku3bee-trailer-latest.mp4"])
        
        size = os.path.getsize(final)
        dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", final], capture_output=True, text=True, timeout=10)
        
        print(f"\n=== TRAILER v5 COMPLETE ===")
        print(f"File: {final}")
        print(f"Size: {size/1024/1024:.1f} MB")
        print(f"Duration: {dur.stdout.strip()}s")
        print(f"URL: http://87.58.149.157/ku3bee-trailer-latest.mp4")
    else:
        print("Final assembly failed")
else:
    print("Video assembly failed")
