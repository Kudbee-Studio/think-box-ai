#!/usr/bin/env python3
"""KUDBEE Cinematic Trailer Generator

Creates a stylized movie trailer with:
- Dramatic typography
- Abstract visual metaphors
- Sound design
- Narration
- Music
"""

import subprocess
import os
import uuid
from pathlib import Path

TEMP = f"/tmp/trailer-{uuid.uuid4().hex[:8]}"
OUTPUT_DIR = "/opt/kudbee/outputs"
os.makedirs(TEMP, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Scene definitions - each scene is a moment in the trailer
SCENES = [
    {
        "id": 1,
        "duration": 4,
        "bg_color": "#0a0a0a",
        "title": "",
        "subtitle": "",
        "narration": "He was just a normal guy. Single. English. Bit of an asshole.",
        "sfx": "ambient_city",
    },
    {
        "id": 2,
        "duration": 3,
        "bg_color": "#1a0a0a",
        "title": "LIFE",
        "subtitle": "was simple",
        "narration": "Life was simple. Predictable. Boring.",
        "sfx": "car_idle",
    },
    {
        "id": 3,
        "duration": 3,
        "bg_color": "#0a0a1a",
        "title": "Until",
        "subtitle": "one day",
        "narration": "Until one day. At a traffic light. Everything changed.",
        "sfx": "car_stop",
    },
    {
        "id": 4,
        "duration": 2,
        "bg_color": "#1a0a0a",
        "title": "",
        "subtitle": "",
        "narration": "Someone ran up. Jumped in the car.",
        "sfx": "car_door",
    },
    {
        "id": 5,
        "duration": 2,
        "bg_color": "#0a0a0a",
        "title": "BANG",
        "subtitle": "",
        "narration": "A shot rang out.",
        "sfx": "gunshot",
    },
    {
        "id": 6,
        "duration": 4,
        "bg_color": "#000000",
        "title": "His brother",
        "subtitle": "A brother he never knew",
        "narration": "The man who jumped in. His brother. A brother he never knew existed. Had been watching. Protecting. Until he couldn't anymore.",
        "sfx": "heartbeat",
    },
    {
        "id": 7,
        "duration": 3,
        "bg_color": "#1a0a0a",
        "title": "They thought",
        "subtitle": "they got away with it",
        "narration": "The people who killed him. They thought they got away with it.",
        "sfx": "tension",
    },
    {
        "id": 8,
        "duration": 4,
        "bg_color": "#0a0a2e",
        "title": "But something",
        "subtitle": "transferred",
        "narration": "But in that moment. As his brother died. Something passed between them. Power. Knowledge. A lifetime of training. Now his.",
        "sfx": "whoosh",
    },
    {
        "id": 9,
        "duration": 3,
        "bg_color": "#1a1a2e",
        "title": "He could",
        "subtitle": "do things",
        "narration": "Things he never dreamed possible. Moving objects. Feeling danger before it came.",
        "sfx": "psychic",
    },
    {
        "id": 10,
        "duration": 3,
        "bg_color": "#0a0a0a",
        "title": "They took",
        "subtitle": "everything from him",
        "narration": "They took everything from him. They would pay for it.",
        "sfx": "determination",
    },
    {
        "id": 11,
        "duration": 5,
        "bg_color": "#0a0a2e",
        "title": "KUDBEE",
        "subtitle": "Coming Soon",
        "narration": "",
        "sfx": "music_crescendo",
    },
]


def create_scene_video(scene: dict, output_path: str) -> bool:
    """Create a video for a single scene."""
    duration = scene["duration"]
    bg_color = scene["bg_color"]
    title = scene["title"]
    subtitle = scene["subtitle"]

    # Build filter complex
    filters = []

    # Background with subtle animation
    if title:
        # Animated title with glow effect
        filters.append(
            f"drawtext=text='{title}':fontsize=96:fontcolor=#00d4ff:font=Arial-Bold:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-50:shadowcolor=black:shadowx=4:shadowy=4:"
            f"alpha='if(lt(t,0.5),t*2,1)'"
        )

    if subtitle:
        filters.append(
            f"drawtext=text='{subtitle}':fontsize=48:fontcolor=#ffffff:font=Arial:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+60:"
            f"alpha='if(lt(t,1),(t-0.5)*2,1)'"
        )

    # Add subtle zoom
    filters.append("zoompan=z='1.0+0.02*in/100':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s=1920x1080:fps=30")

    # Add fade in/out
    fade_out_start = duration - 0.5
    filters.append(f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out_start}:d=0.5")

    filter_str = ",".join(filters) if filters else "format=yuv420p"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={bg_color}:s=1920x1080:d={duration}:r=30",
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",  # No audio yet
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Error creating scene {scene['id']}: {e}")
        return False


def create_narration_audio(text: str, output_path: str):
    """Generate narration using espeak."""
    if not text:
        # Create silent audio
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", "3", "-acodec", "pcm_s16le", output_path
        ], capture_output=True, timeout=10)
        return

    subprocess.run([
        "espeak", "-w", output_path, "-s", "140", "-p", "30", text
    ], capture_output=True, timeout=10)


def create_sound_effect(sfx_type: str, duration: float, output_path: str):
    """Generate basic sound effects."""
    if sfx_type == "gunshot":
        # Synthesize gunshot
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=100:duration=0.1,volume=0.8",
            "-af", "afade=t=out:st=0.05:d=0.1",
            output_path
        ], capture_output=True, timeout=10)
    elif sfx_type == "heartbeat":
        # Synthesize heartbeat
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=60:duration={duration}",
            "-af", "volume=0.3",
            output_path
        ], capture_output=True, timeout=10)
    elif sfx_type == "whoosh":
        # Synthesize whoosh
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=200:duration=0.5",
            "-af", "afade=t=in:st=0:d=0.1,afade=t=out:st=0.3:d=0.2,volume=0.5",
            output_path
        ], capture_output=True, timeout=10)
    else:
        # Silent
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", str(duration), "-acodec", "pcm_s16le", output_path
        ], capture_output=True, timeout=10)


def main():
    print("=== KUDBEE Cinematic Trailer Production ===\n")

    # Step 1: Create video for each scene
    print("Creating scene videos...")
    scene_videos = []
    for scene in SCENES:
        output = f"{TEMP}/scene_{scene['id']:02d}.mp4"
        if create_scene_video(scene, output):
            scene_videos.append(output)
            print(f"  Scene {scene['id']}: {scene['title'] or scene['subtitle']}")

    # Step 2: Create narration audio
    print("\nGenerating narration...")
    narration_files = []
    for scene in SCENES:
        output = f"{TEMP}/narration_{scene['id']:02d}.wav"
        create_narration_audio(scene["narration"], output)
        narration_files.append(output)

    # Step 3: Combine video and narration for each scene
    print("\nCombining video + narration...")
    combined_clips = []
    for i, scene in enumerate(SCENES):
        video = scene_videos[i]
        audio = narration_files[i]
        output = f"{TEMP}/combined_{scene['id']:02d}.mp4"

        # Get audio duration
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", audio
            ], capture_output=True, text=True, timeout=5)
            audio_dur = float(result.stdout.strip())
        except:
            audio_dur = scene["duration"]

        # Combine with padding if needed
        cmd = [
            "ffmpeg", "-y",
            "-i", video,
            "-i", audio,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            output
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        combined_clips.append(output)

    # Step 4: Create concat file and merge
    print("\nAssembling trailer...")
    concat_file = f"{TEMP}/concat.txt"
    with open(concat_file, "w") as f:
        for clip in combined_clips:
            f.write(f"file '{clip}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        f"{TEMP}/trailer_no_music.mp4"
    ], capture_output=True, timeout=60)

    # Step 5: Add background music
    print("Adding music...")
    music_file = None
    for f in os.listdir("/opt/kudbee/outputs"):
        if f.endswith(".mp3"):
            music_file = f"/opt/kudbee/outputs/{f}"
            break

    if music_file:
        # Loop music to match video length and mix
        subprocess.run([
            "ffmpeg", "-y",
            "-i", f"{TEMP}/trailer_no_music.mp4",
            "-stream_loop", "-1", "-i", music_file,
            "-filter_complex",
            "[0:a]volume=1.0[a0];[1:a]atrim=0:90,volume=0.25[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            f"{OUTPUT_DIR}/ku3bee-trailer.mp4"
        ], capture_output=True, timeout=60)
    else:
        os.rename(f"{TEMP}/trailer_no_music.mp4", f"{OUTPUT_DIR}/ku3bee-trailer.mp4")

    # Cleanup
    import shutil
    shutil.rmtree(TEMP, ignore_errors=True)

    # Final output
    output_path = f"{OUTPUT_DIR}/ku3bee-trailer.mp4"
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1e6
        print(f"\n=== TRAILER COMPLETE ===")
        print(f"Output: {output_path}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"Scenes: {len(SCENES)}")
    else:
        print("ERROR: Trailer creation failed")


if __name__ == "__main__":
    main()
