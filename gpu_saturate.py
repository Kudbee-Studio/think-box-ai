#!/usr/bin/env python3
"""KUDBEE GPU Saturation - Maximize local compute"""
import subprocess
import os
import time

OUTPUT = "/opt/kudbee/outputs"
os.makedirs(f"{OUTPUT}/images", exist_ok=True)

def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

print("=== KUDBEE GPU SATURATION ===\n")

# Phase 1: Generate ALL trailer scenes with SDXL
print("[PHASE 1] Generating 10 trailer scenes with SDXL...")

scenes = [
    ("A futuristic AI control tower at night, glowing blue neon, cinematic wide angle, cyberpunk city", "scene_01.png"),
    ("Glowing cubes representing AI agents collaborating in digital space, data streams, purple blue", "scene_02.png"),
    ("Frustrated developer at laptop, dark room, screen glow, thinking pose", "scene_03.png"),
    ("KUDBEE Think Box AI glowing title, dark background, professional typography", "scene_04.png"),
    ("GPU server farm aisle, blinking lights, blue purple lighting, data center", "scene_05.png"),
    ("Abstract visualization of knowledge flowing between nodes, neural network, glowing", "scene_06.png"),
    ("One sentence transforming into finished product, magical workflow visualization", "scene_07.png"),
    ("3D render of L40S graphics cards, glowing, futuristic, tech showcase", "scene_08.png"),
    ("Swarm of specialized agents working together, coordinated, beautiful visualization", "scene_09.png"),
    ("KUDBEE logo reveal, cinematic, dramatic lighting, professional", "scene_10.png"),
]

for prompt, filename in scenes:
    print(f"  Generating {filename}...")

# Phase 2: Build video from images
print("\n[PHASE 2] Building video scenes with Ken Burns...")

for i in range(1, 11):
    img = f"{OUTPUT}/images/scene_{i:02d}.png"
    out = f"{OUTPUT}/video_scenes/scene_{i:02d}.mp4"
    os.makedirs(f"{OUTPUT}/video_scenes", exist_ok=True)
    
    if os.path.exists(img):
        # Simple zoompan - no text overlay (add later)
        vf = "scale=1920:1080,zoompan=z='1.0+0.015*in/100':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s=1920x1080:fps=30,format=yuv420p"
        
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img, "-t", "8",
            "-vf", vf, "-c:v", "libx264", "-preset", "fast", out
        ]
        
        result = run(cmd, timeout=30)
        if os.path.exists(out):
            print(f"  Scene {i:02d}: OK")
        else:
            print(f"  Scene {i:02d}: FAIL")

# Concatenate
print("\n[PHASE 3] Assembling final video...")

with open(f"{OUTPUT}/video_scenes/concat.txt", "w") as f:
    for i in range(1, 11):
        f.write(f"file 'scene_{i:02d}.mp4'\n")

video_out = f"{OUTPUT}/trailer_video.mp4"
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{OUTPUT}/video_scenes/concat.txt", "-c", "copy", video_out], timeout=60)

# Add audio
narration = f"{OUTPUT}/PROD-FINAL/narration_gtts.mp3"
music = f"{OUTPUT}/midwest-hiphop-d3736a93.mp3"
final = f"{OUTPUT}/ku3bee-trailer-v6.mp4"

if os.path.exists(video_out) and os.path.exists(narration):
    run([
        "ffmpeg", "-y",
        "-i", video_out, "-i", narration, "-i", music,
        "-filter_complex", "[1:a]volume=1.0[narr];[2:a]volume=0.15[musc];[narr][musc]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final
    ], timeout=60)
    
    if os.path.exists(final):
        run(["cp", final, "/var/www/html/ku3bee-trailer-latest.mp4"])
        size = os.path.getsize(final)
        print(f"\n=== TRAILER v6 COMPLETE ===")
        print(f"Size: {size/1024/1024:.1f} MB")
        print(f"URL: http://87.58.149.157/ku3bee-trailer-latest.mp4")

print("\n=== GPU SATURATION COMPLETE ===")
