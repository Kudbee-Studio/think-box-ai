# Phase 2: Full-Length AI Film Production

**Goal:** Produce a 90-minute feature-quality film using AI-generated video, professional narration, and cinematic post-production.

---

## Current State (Phase 1)

| Component | Status | Output |
|-----------|--------|--------|
| Agent Runtime | ✅ Docker-harnessed | Isolated tool execution |
| Autonomous Loop | ✅ Running | Task generation + execution |
| Governance | ✅ Dashboard | Agent state tracking |
| Video Production | ⚠️ Basic | 80-second trailer (FFmpeg slideshow) |
| Voice Narration | ⚠️ espeak | Robotic TTS |
| Music | ✅ ACE-Step | AI-generated background music |

---

## Research: State of the Art (2026)

### Video Generation Models

| Model | Params | VRAM | Clip Length | License | Best For |
|-------|--------|------|-------------|---------|----------|
| **Wan2.2-TI2V-5B** | 5B | ~12GB | 5s @ 720p | Apache 2.0 | Consumer hardware, commercial use |
| **HunyuanVideo** | 13B | ~60GB | 5s @ 720p | Tencent Community | Best motion quality |
| **Wan2.2-T2V-A14B-GGUF** | 14B | ~8-10GB | 5s @ 720p | Apache 2.0 | Low VRAM, quantized |
| **LTX-Video** | 2B | ~8GB | 5s @ 720p | MIT | Image-to-video animation |
| **CogVideoX** | 5B | ~12GB | 5s @ 720p | Apache 2.0 | Bilingual (EN/CN) |

### Long-Form Generation Research

| Approach | Description | Status |
|----------|-------------|--------|
| **Autoregressive Diffusion** | Condition new frames on previous output | Production-ready |
| **TetherCache** | KV-cache management for drift resistance | Research (2025) |
| **Visko Orbis** | Real-time interactive long video | Research (2026) |
| **Streaming Chunk-wise** | Generate in chunks with bounded memory | Production-ready |

### Voice Generation

| Tool | Quality | Cost | Best For |
|------|---------|------|----------|
| **ElevenLabs** | ⭐⭐⭐⭐⭐ | $5-330/mo | Professional narration, voice cloning |
| **OpenAI TTS** | ⭐⭐⭐⭐ | $0.015/1K chars | Fast, natural |
| **Coqui TTS** | ⭐⭐⭐ | Free (self-hosted) | Open source, customizable |

---

## Phase 2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FILM PRODUCTION PIPELINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SCRIPT GENERATION (Host - LLM)                              │
│     ├─ GPT-OSS-120B: Full screenplay (90 min)                   │
│     ├─ Scene breakdown: ~180 scenes × 30s each                  │
│     └─ Character definitions + arc tracking                      │
│                                                                  │
│  2. STORYBOARD (Container - Image Gen)                          │
│     ├─ FLUX.1 / SDXL: Keyframe per scene                        │
│     ├─ Character reference sheets                                │
│     └─ Camera direction notes                                    │
│                                                                  │
│  3. SCENE GENERATION (GPU - Video Model)                         │
│     ├─ Wan2.2-TI2V-5B per scene (30s each)                     │
│     ├─ Image-to-video for consistency                            │
│     ├─ Parallel across 3x L40S GPUs                             │
│     └─ ~9 min per scene = ~27 hours total                       │
│                                                                  │
│  4. VOICE PRODUCTION (API - ElevenLabs)                         │
│     ├─ Character voice profiles                                  │
│     ├─ Emotion-tagged narration                                  │
│     └─ Lip-sync alignment                                        │
│                                                                  │
│  5. POST-PRODUCTION (FFmpeg + GPU)                              │
│     ├─ Scene assembly + transitions                              │
│     ├─ Color grading                                             │
│     ├─ Sound design + music (ACE-Step)                          │
│     └─ Final mix + master                                        │
│                                                                  │
│  6. QUALITY ASSURANCE (Agent + Human)                           │
│     ├─ Continuity checking                                       │
│     ├─ Character consistency validation                          │
│     └─ Narrative coherence scoring                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## GPU Resource Planning

### 3x NVIDIA L40S (46GB VRAM each)

| GPU | Task | VRAM Usage |
|-----|------|------------|
| **GPU 0** | LLM Inference (GPT-OSS-120B) | ~40GB |
| **GPU 1** | Video Generation (Wan2.2) | ~12GB |
| **GPU 2** | Image Generation + Post | ~8GB |

### Storage Requirements

| Asset Type | Per Scene | Total (180 scenes) |
|------------|-----------|-------------------|
| Storyboard images | 2MB | 360MB |
| Raw video (720p) | 50MB | 9GB |
| Final video (1080p) | 100MB | 18GB |
| Audio (narration) | 5MB | 900MB |
| **Total** | **~157MB** | **~28.3GB** |

---

## Implementation Plan

### STEP 1: Video Model Integration

**Goal:** Integrate Wan2.2-TI2V-5B for scene generation

```python
# core/video/generator.py
class VideoGenerator:
    def __init__(self, model="Wan-AI/Wan2.2-TI2V-5B-Diffusers"):
        self.pipe = DiffusionPipeline.from_pretrained(
            model, torch_dtype=torch.bfloat16
        ).to("cuda")
    
    def generate_scene(self, prompt, image=None, duration=5):
        """Generate a 5-second scene from prompt + optional keyframe"""
        video = self.pipe(
            prompt=prompt,
            image=image,  # For image-to-video
            num_frames=81,  # 5s @ 16fps
            height=720,
            width=1280,
        ).frames[0]
        return video  # Returns tensor
```

**Tasks:**
- [ ] Install Diffusers + Wan2.2 dependencies
- [ ] Download model to /mnt/models (500GB disk)
- [ ] Create VideoGenerator class
- [ ] Add to tool registry (sandboxed via harness)
- [ ] Test single scene generation

### STEP 2: Script Decomposition

**Goal:** Break screenplay into generation-ready scenes

```python
# core/video/script_parser.py
class ScriptParser:
    def parse_screenplay(self, script_text):
        """Parse screenplay into structured scenes"""
        scenes = []
        # Extract: Scene heading, action, dialogue, characters
        return scenes
    
    def generate_scene_prompts(self, scenes):
        """Convert scenes to video generation prompts"""
        prompts = []
        for scene in scenes:
            prompt = {
                "visual": "cinematic, 4k, {description}",
                "characters": ["character descriptions"],
                "camera": "camera movement description",
                "duration": 30,  # seconds
                "style": "film genre style",
            }
            prompts.append(prompt)
        return prompts
```

**Tasks:**
- [ ] Create screenplay template
- [ ] Build script parser
- [ ] Generate scene prompts with character consistency
- [ ] Validate prompt quality

### STEP 3: ElevenLabs Integration

**Goal:** Professional voice narration

```python
# core/audio/voice_generator.py
class VoiceGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.voice_cache = {}
    
    def create_character_voice(self, name, description):
        """Clone or configure voice for a character"""
        voice = elevenlabs.clone(
            name=name,
            description=description,
            labels={"type": "narrator" or "character"}
        )
        self.voice_cache[name] = voice
        return voice
    
    def generate_narration(self, text, character, emotion="neutral"):
        """Generate narration with emotion"""
        audio = elevenlabs.generate(
            text=text,
            voice=self.voice_cache[character],
            model="eleven_multilingual_v2",
            emotion=emotion
        )
        return audio
```

**Tasks:**
- [ ] Set up ElevenLabs API key
- [ ] Define character voice profiles
- [ ] Generate narration per scene
- [ ] Sync with video timing

### STEP 4: Scene Assembly Pipeline

**Goal:** Assemble individual scenes into final film

```python
# core/video/assembler.py
class FilmAssembler:
    def __init__(self):
        self.ffmpeg = FFmpegWrapper()
    
    def assemble_scene(self, video, audio, transitions):
        """Combine video + audio with transitions"""
        # Add fade in/out, cross-dissolves
        pass
    
    def color_grade(self, video, style="cinematic"):
        """Apply LUT / color grading"""
        pass
    
    def add_music(self, video, music_track, duck_factor=0.3):
        """Mix background music with narration"""
        pass
    
    def render_final(self, scenes, output_path):
        """Concatenate all scenes and render master"""
        pass
```

**Tasks:**
- [ ] Create scene transition library
- [ ] Implement color grading pipeline
- [ ] Build audio mixing (narration + music + SFX)
- [ ] Final render with quality control

### STEP 5: Quality Assurance Agent

**Goal:** Automated quality control

```python
# core/video/quality_agent.py
class QualityAgent:
    def check_continuity(self, scene_n, scene_n_plus_1):
        """Check visual continuity between scenes"""
        # Character appearance, lighting, props
        pass
    
    def validate_lip_sync(self, video, audio):
        """Verify lip sync accuracy"""
        pass
    
    def score_narrative_coherence(self, full_script, generated_scenes):
        """LLM-based narrative scoring"""
        pass
```

**Tasks:**
- [ ] Build continuity checker
- [ ] Implement lip-sync validation
- [ ] Create narrative coherence scorer
- [ ] Generate quality report

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| **Step 1: Video Model** | 2-3 days | GPU server running |
| **Step 2: Script Parser** | 1 day | None (local dev) |
| **Step 3: Voice Gen** | 1 day | ElevenLabs API key |
| **Step 4: Assembly** | 2-3 days | Steps 1-3 complete |
| **Step 5: QA** | 1-2 days | Step 4 complete |
| **Production Run** | ~30 hours GPU | All steps complete |
| **Total** | ~7-10 days | |

---

## Cost Estimate

| Resource | Cost |
|----------|------|
| GPU Server (3x L40S) | ~$3.50/hr × 30hrs = $105 |
| ElevenLabs API | ~$22 (Creator plan) |
| Storage (400GB) | Included |
| **Total** | **~$130** |

---

## Risks + Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GPU capacity unavailable | Can't render | Use cloud RunPod/Replicate fallback |
| Character inconsistency | Visual discontinuity | Use reference images + IP-Adapter |
| Long-form quality drift | Boring/repetitive | Chunk generation with quality gates |
| Voice emotion mismatch | Uncanny narration | ElevenLabs emotion control + manual review |
| Scene transition jarring | Amateur look | Cross-dissolve + audio bridge |

---

## Next Actions

1. **When GPU server is available:** Start Step 1 (Wan2.2 integration)
2. **Now:** Implement ScriptParser locally (Step 2)
3. **Now:** Set up ElevenLabs account + voice profiles
4. **After server:** Run test scenes → validate quality → full production
