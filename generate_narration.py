#!/usr/bin/env python3
"""Generate high-quality narration using free TTS APIs"""

import urllib.request
import json
import subprocess
import os

OUTPUT_DIR = "/opt/kudbee/outputs/PROD-FINAL"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NARRATION = """What if your ideas could build themselves?
KUDBEE. An operating environment where specialized agents collaborate.
Think Boxes deploy to write, code, design, and analyze.
Each one persistent. Each one purpose-built.
They remember what they learn.
One sentence in. Finished production out.
KUDBEE. Think Box AI."""

def try_voice_ai_api():
    """Try Voice.ai free API."""
    try:
        # Voice.ai has a free tier API
        data = json.dumps({
            "text": NARRATION,
            "voice": "male_professional",
            "format": "mp3"
        }).encode()
        
        req = urllib.request.Request(
            "https://api.voice.ai/v1/tts",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                with open(f"{OUTPUT_DIR}/narration_ai.mp3", "wb") as f:
                    f.write(resp.read())
                return True
    except:
        pass
    return False

def try_ttsmaker_api():
    """Try TTSMaker free API (20K chars/week)."""
    try:
        # TTSMaker API endpoint
        params = {
            "text": NARRATION,
            "voice": "en-US-Standard-C",
            "format": "mp3"
        }
        
        url = "https://ttsmaker.com/api/tts?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 0:
                with open(f"{OUTPUT_DIR}/narration_ai.mp3", "wb") as f:
                    f.read()
                return True
    except:
        pass
    return False

def try_google_tts_api():
    """Try Google Translate TTS (free, no API key needed)."""
    try:
        from gtts import gTTS
        
        tts = gTTS(text=NARRATION, lang='en', slow=False)
        tts.save(f"{OUTPUT_DIR}/narration_ai.mp3")
        
        return os.path.exists(f"{OUTPUT_DIR}/narration_ai.mp3")
    except:
        pass
    return False

def generate_with_coqui():
    """Use Coqui TTS (local, if installed)."""
    try:
        from TTS.api import TTS
        
        tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
        tts.tts_to_file(text=NARRATION, file_path=f"{OUTPUT_DIR}/narration_coqui.wav")
        
        return os.path.exists(f"{OUTPUT_DIR}/narration_coqui.wav")
    except:
        pass
    return False

def main():
    print("=== Generating High-Quality Narration ===")
    
    methods = [
        ("Google TTS (gTTS)", try_google_tts_api),
        ("Coqui TTS (local)", generate_with_coqui),
    ]
    
    for name, method in methods:
        print(f"Trying {name}...")
        if method():
            print(f"  SUCCESS with {name}")
            return True
        print(f"  Failed")
    
    print("\nAll AI methods failed. Using enhanced eSpeak with better parameters...")
    return generate_enhanced_espeak()

def generate_enhanced_espeak():
    """Enhanced eSpeak with better parameters."""
    wav_file = f"{OUTPUT_DIR}/narration_enhanced.wav"
    mp3_file = f"{OUTPUT_DIR}/narration_enhanced.mp3"
    
    # Break into segments for better pacing
    segments = NARRATION.strip().split(". ")
    
    segment_files = []
    for i, segment in enumerate(segments):
        if not segment.strip():
            continue
        
        seg_wav = f"{OUTPUT_DIR}/seg_{i:02d}.wav"
        
        # Enhanced eSpeak with better pitch and speed
        cmd = [
            "espeak", "-w", seg_wav,
            "-s", "130",  # Speed (words per minute)
            "-p", "60",   # Pitch (0-100)
            "-a", "200",  # Amplitude
            "-g", "5",    # Gap between words
            segment.strip()
        ]
        
        subprocess.run(cmd, capture_output=True, timeout=30)
        
        if os.path.exists(seg_wav):
            segment_files.append(seg_wav)
            # Add small silence between segments
            silence = f"{OUTPUT_DIR}/silence_{i:02d}.wav"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                "anullsrc=r=22050:cl=mono", "-t", "0.5",
                "-acodec", "pcm_s16le", silence
            ], capture_output=True, timeout=10)
            segment_files.append(silence)
    
    # Concatenate all segments
    with open(f"{OUTPUT_DIR}/concat_list.txt", "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")
    
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", f"{OUTPUT_DIR}/concat_list.txt",
        "-acodec", "pcm_s16le", wav_file
    ], capture_output=True, timeout=30)
    
    # Convert to MP3
    subprocess.run([
        "ffmpeg", "-y", "-i", wav_file,
        "-codec:a", "libmp3lame", "-qscale:a", "3",
        mp3_file
    ], capture_output=True, timeout=30)
    
    if os.path.exists(mp3_file):
        size = os.path.getsize(mp3_file)
        print(f"Enhanced eSpeak narration: {size/1024:.0f} KB")
        return True
    
    return False

if __name__ == "__main__":
    main()
