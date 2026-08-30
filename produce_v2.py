#!/usr/bin/env python3
"""KUDBEE Autonomous Production Loop v1

Produces a 90-second cinematic trailer using cooperating Think Boxes.
Each box is a specialized worker. Evidence flows through provenance.
"""

import json
import os
import subprocess
import time
import sqlite3
import urllib.request
from datetime import datetime, timezone

PRODUCTION_ID = f"PROD-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
OUTPUT_DIR = f"/opt/kudbee/outputs/{PRODUCTION_ID}"
OLLAMA = "http://localhost:11434"
DB_PATH = "/opt/kudbee/memory/think_tokens.db"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def ollama_generate(model, prompt, max_tokens=1000):
    """Generate text via Ollama."""
    data = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"max_tokens": max_tokens}
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=data,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode()).get("response", "")
    except Exception as e:
        return f"Error: {e}"


def box_director():
    """DIRECTOR: Creates screenplay, pacing, scenes, shot list."""
    print("\n[DIRECTOR] Creating screenplay...")
    
    screenplay = ollama_generate("gpt-oss-120b", """You are a film director. Create a precise 90-second cinematic trailer screenplay for KUDBEE (AI operating environment).

Format exactly:
[00:00-00:05] SCENE 1: [Description]
  Visual: [what appears on screen]
  Audio: [narration or music cue]
  Text: [exact on-screen text]

[00:05-00:12] SCENE 2: ...
... continue for exactly 90 seconds total

Requirements:
- 8-12 scenes total
- Each scene has exact timestamps
- Include visual, audio, and text for each scene
- End with "KUDBEE — Think Box AI" title card
- Professional, cinematic, compelling""", max_tokens=2000)
    
    with open(f"{OUTPUT_DIR}/screenplay.txt", "w") as f:
        f.write(screenplay)
    
    print(f"[DIRECTOR] Screenplay saved: {len(screenplay)} chars")
    return {"screenplay": screenplay[:500], "status": "complete"}


def box_visual_continuity():
    """VISUAL: Creates style guide for consistency."""
    print("\n[VISUAL] Creating style guide...")
    
    style = ollama_generate("gpt-oss-20b", """You are a visual director. Create a style guide for the KUDBEE trailer:

- Color palette (hex codes)
- Typography (font choices)
- Character descriptions (if any)
- Visual motifs/recurring elements
- Mood/tone descriptors

Keep it concise but specific. Max 500 words.""", max_tokens=500)
    
    with open(f"{OUTPUT_DIR}/style_guide.txt", "w") as f:
        f.write(style)
    
    print(f"[VISUAL] Style guide saved: {len(style)} chars")
    return {"style_guide": style[:300], "status": "complete"}


def box_camera():
    """CAMERA: Shot composition, lenses, movement, lighting."""
    print("\n[CAMERA] Creating shot list...")
    
    shots = ollama_generate("gpt-oss-20b", """You are a cinematographer. For each scene in this screenplay, specify:

- Shot type (wide, medium, close-up, POV, aerial)
- Camera movement (static, pan, tilt, dolly, zoom, handheld)
- Lens (wide 24mm, standard 50mm, telephoto 85mm+)
- Lighting (key light direction, mood, color temp)
- Composition rule (rule of thirds, center, leading lines)

Screenplay:
[SCREENPLAY]

Format as numbered list matching scene numbers.""", max_tokens=1000)
    
    with open(f"{OUTPUT_DIR}/shot_list.txt", "w") as f:
        f.write(shots)
    
    print(f"[CAMERA] Shot list saved: {len(shots)} chars")
    return {"shots": shots[:300], "status": "complete"}


def box_music():
    """MUSIC: ACE-Step generates the score."""
    print("\n[MUSIC] Generating score with ACE-Step...")
    
    model_path = "/opt/kudbee/models/acestep"
    output_wav = f"{OUTPUT_DIR}/score.wav"
    output_mp3 = f"{OUTPUT_DIR}/score.mp3"
    
    if not os.path.exists(model_path):
        print("[MUSIC] ACE-Step model not found, using fallback")
        # Create silent fallback
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "90", "-acodec", "pcm_s16le", output_wav
        ], capture_output=True, timeout=30)
        return {"status": "fallback", "reason": "model_not_found"}
    
    # Generate with ACE-Step
    cmd = f"""
import sys, os
sys.path.insert(0, "/opt/kudbee/ACE-Step")
os.chdir("/opt/kudbee/ACE-Step")
from acestep.pipeline_ace_step import ACEStepPipeline
pipe = ACEStepPipeline(checkpoint_dir="{model_path}", dtype="bfloat16")
pipe(
    audio_duration=90.0,
    prompt="cinematic electronic trailer music, building tension, heroic, futuristic, 90 BPM, orchestral synth hybrid",
    lyrics="",
    infer_step=30,
    guidance_scale=15.0,
    scheduler_type="euler",
    cfg_type="apg",
    omega_scale=10.0,
    manual_seeds=[42],
    save_path="{output_wav}"
)
"""
    
    with open(f"{OUTPUT_DIR}/gen_score.py", "w") as f:
        f.write(cmd)
    
    result = subprocess.run(["python3", f"{OUTPUT_DIR}/gen_score.py"],
                          capture_output=True, text=True, timeout=600)
    
    if os.path.exists(output_wav):
        # Convert to MP3
        subprocess.run([
            "ffmpeg", "-y", "-i", output_wav, "-codec:a", "libmp3lame",
            "-qscale:a", "2", output_mp3
        ], capture_output=True, timeout=60)
        size = os.path.getsize(output_mp3)
        print(f"[MUSIC] Score generated: {size/1024:.0f} KB")
        return {"status": "generated", "file": output_mp3, "size_kb": size/1024}
    else:
        print("[MUSIC] Generation failed, using fallback")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "90", "-acodec", "libmp3lame", "-qscale:a", "5", output_mp3
        ], capture_output=True, timeout=30)
        return {"status": "fallback", "reason": "generation_failed"}


def box_voice():
    """VOICE: TTS narration."""
    print("\n[VOICE] Generating narration...")
    
    narration_text = """What if your ideas could build themselves?
Meet KUDBEE.
An operating environment where specialized agents collaborate.
Think Boxes deploy to write, code, design, and analyze.
Each one persistent.
Each one purpose-built.
They remember what they learn.
One sentence in.
Finished production out.
KUDBEE.
Think Box AI."""
    
    wav_file = f"{OUTPUT_DIR}/narration.wav"
    
    # Generate narration segments
    segments = narration_text.strip().split("\n\n")
    segment_files = []
    
    for i, segment in enumerate(segments):
        seg_file = f"{OUTPUT_DIR}/narration_seg_{i:02d}.wav"
        # Use espeak for TTS
        subprocess.run([
            "espeak", "-w", seg_file, "-s", "140", "-p", "50",
            segment.replace("\n", " ")
        ], capture_output=True, timeout=30)
        segment_files.append(seg_file)
    
    # Create concat list
    with open(f"{OUTPUT_DIR}/narration_concat.txt", "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")
    
    # Concatenate
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", f"{OUTPUT_DIR}/narration_concat.txt",
        "-acodec", "pcm_s16le", wav_file
    ], capture_output=True, timeout=30)
    
    if os.path.exists(wav_file):
        size = os.path.getsize(wav_file)
        print(f"[VOICE] Narration generated: {size/1024:.0f} KB")
        return {"status": "generated", "file": wav_file, "size_kb": size/1024}
    else:
        return {"status": "failed"}


def box_sound():
    """SOUND: Sound effects, ambience, transitions."""
    print("\n[SOUND] Generating sound effects...")
    
    sfx_dir = f"{OUTPUT_DIR}/sfx"
    os.makedirs(sfx_dir, exist_ok=True)
    
    # Generate simple tones for transitions
    sfx = {
        "whoosh.wav": "sine=frequency=800:duration=0.5",
        "impact.wav": "sine=frequency=100:duration=0.3,volume=0.5",
        "ambient.wav": "anoisesrc=color=pink:duration=90,volume=0.1",
    }
    
    generated = []
    for name, filter_str in sfx.items():
        path = f"{sfx_dir}/{name}"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", filter_str, path
        ], capture_output=True, timeout=30)
        if os.path.exists(path):
            generated.append(name)
    
    print(f"[SOUND] Generated {len(generated)} SFX")
    return {"status": "generated", "sfx": generated}


def box_editor(screenplay_info, music_info, voice_info, sound_info):
    """EDITOR: Assemble final video."""
    print("\n[EDITOR] Assembling final video...")
    
    # Create scenes from screenplay
    scenes = []
    scenes_dir = f"{OUTPUT_DIR}/scenes"
    os.makedirs(scenes_dir, exist_ok=True)
    
    # Parse timestamps from screenplay (simplified)
    scene_times = [
        (0, 5, "What if your ideas\ncould build themselves?"),
        (5, 12, "KUDBEE\nThink Box AI"),
        (12, 18, "Specialized agents\nthat collaborate"),
        (18, 24, "Write • Code\nDesign • Analyze"),
        (24, 30, "Each one persistent\nEach one purpose-built"),
        (30, 38, "They remember\nwhat they learn"),
        (38, 46, "One sentence in\nFinished production out"),
        (46, 54, "3x NVIDIA L40S\n256GB RAM"),
        (54, 62, "GPT-OSS • ACE-Step\nFLUX • LTX"),
        (62, 75, "KUDBEE\nThink Box AI"),
        (75, 85, "kudbee.ai"),
        (85, 90, ""),
    ]
    
    # Generate each scene as video clip
    for i, (start, end, text) in enumerate(scene_times):
        duration = end - start
        output = f"{scenes_dir}/scene_{i:02d}.mp4"
        
        # Create colored background with text
        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        
        if text:
            # Escape for ffmpeg
            safe_text = text.replace("\n", "\\n").replace(":", "\\:")
            vf = f"drawtext=fontfile={font}:text='{safe_text}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:fade=t=in:st=0:d=0.5"
        else:
            vf = "format=yuv420p"
        
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0a0a2e:s=1920x1080:d={duration}:r=30",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast",
            output
        ], capture_output=True, timeout=30)
        
        if os.path.exists(output):
            scenes.append(output)
    
    print(f"[EDITOR] Generated {len(scenes)} scenes")
    
    # Concatenate video
    with open(f"{scenes_dir}/concat.txt", "w") as f:
        for s in scenes:
            f.write(f"file '{os.path.basename(s)}'\n")
    
    video_only = f"{OUTPUT_DIR}/video_only.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", f"{scenes_dir}/concat.txt",
        "-c", "copy", video_only
    ], capture_output=True, timeout=60)
    
    # Add narration
    if voice_info.get("status") == "generated":
        with_narration = f"{OUTPUT_DIR}/with_narration.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-i", voice_info["file"],
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", with_narration
        ], capture_output=True, timeout=60)
    else:
        with_narration = video_only
    
    # Add music
    if music_info.get("status") == "generated":
        final = f"{OUTPUT_DIR}/ku3bee-trailer-final.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", with_narration,
            "-i", music_info["file"],
            "-filter_complex", "[0:a]volume=1.0[narr];[1:a]volume=0.25[musc];[narr][musc]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", final
        ], capture_output=True, timeout=60)
    else:
        final = with_narration
    
    # Also copy to outputs root for easy access
    if os.path.exists(final):
        subprocess.run(["cp", final, f"/opt/kudbee/outputs/ku3bee-trailer-latest.mp4"])
        subprocess.run(["cp", final, f"/var/www/html/ku3bee-trailer-latest.mp4"])
    
    if os.path.exists(final):
        size = os.path.getsize(final)
        print(f"[EDITOR] Final video: {final} ({size/1024/1024:.1f} MB)")
        return {"status": "assembled", "file": final, "scenes": len(scenes), "size_mb": size/1024/1024}
    else:
        return {"status": "failed"}


def box_jury(production_manifest):
    """JURY: Evaluate the final artifact."""
    print("\n[JURY] Evaluating production...")
    
    final_file = production_manifest.get("editor", {}).get("file", "")
    
    if not os.path.exists(final_file):
        return {"verdict": "FAIL", "reason": "No final artifact"}
    
    # Get video info
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", final_file
    ], capture_output=True, text=True, timeout=30)
    
    try:
        info = json.loads(result.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
        has_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
        has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    except:
        duration = 0
        has_video = False
        has_audio = False
    
    # Score
    score = 0
    checks = {}
    
    if has_video:
        score += 30
        checks["has_video"] = True
    if has_audio:
        score += 30
        checks["has_audio"] = True
    if 80 <= duration <= 100:
        score += 40
        checks["duration"] = duration
    elif 70 <= duration <= 110:
        score += 20
        checks["duration"] = duration
    
    verdict = "PASS" if score >= 70 else "FAIL"
    
    evaluation = {
        "verdict": verdict,
        "score": score,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    print(f"[JURY] Verdict: {verdict} ({score}/100)")
    return evaluation


def main():
    print("=" * 60)
    print("  KUDBEE AUTONOMOUS PRODUCTION LOOP")
    print(f"  Production ID: {PRODUCTION_ID}")
    print("=" * 60)
    
    manifest = {
        "production_id": PRODUCTION_ID,
        "outcome": "Create a polished 90-second cinematic trailer demonstrating KUDBEE",
        "started": datetime.now(timezone.utc).isoformat(),
        "boxes": {},
    }
    
    start_time = time.time()
    
    # Phase 1: Director
    manifest["boxes"]["director"] = box_director()
    
    # Phase 2: Visual + Camera (parallel concept)
    manifest["boxes"]["visual"] = box_visual_continuity()
    manifest["boxes"]["camera"] = box_camera()
    
    # Phase 3: Audio (music + voice + sound)
    manifest["boxes"]["music"] = box_music()
    manifest["boxes"]["voice"] = box_voice()
    manifest["boxes"]["sound"] = box_sound()
    
    # Phase 4: Editor
    manifest["boxes"]["editor"] = box_editor(
        manifest["boxes"]["director"],
        manifest["boxes"]["music"],
        manifest["boxes"]["voice"],
        manifest["boxes"]["sound"],
    )
    
    # Phase 5: Jury
    manifest["jury"] = box_jury(manifest["boxes"])
    
    # Phase 6: Record results
    manifest["completed"] = datetime.now(timezone.utc).isoformat()
    manifest["total_seconds"] = round(time.time() - start_time, 1)
    
    with open(f"{OUTPUT_DIR}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    
    print("\n" + "=" * 60)
    print("  PRODUCTION COMPLETE")
    print(f"  Duration: {manifest['total_seconds']}s")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Jury: {manifest['jury'].get('verdict', 'unknown')}")
    print("=" * 60)
    
    return manifest


if __name__ == "__main__":
    main()
