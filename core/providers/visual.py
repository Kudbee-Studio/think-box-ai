"""KUDBEE Visual Provider Abstraction

Implements Provider Independence principle from AGENTS.md:
- No model provider is hardcoded
- Swapping a provider is a configuration change, not a code change
- Runtime only knows the VisualProvider protocol
"""

from __future__ import annotations

import os
import json
import time
import uuid
import subprocess
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ImageSpec:
    """Specification for image generation."""
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    seed: int = -1
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    reference_image: Optional[str] = None
    character_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoSpec:
    """Specification for video generation."""
    prompt: str
    duration_seconds: float = 5.0
    fps: int = 24
    width: int = 1280
    height: int = 720
    seed: int = -1
    reference_image: Optional[str] = None
    reference_video: Optional[str] = None
    character_id: Optional[str] = None
    camera_shot: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceSpec:
    """Specification for voice generation."""
    text: str
    voice_id: str = "default"
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0
    emotion: str = "neutral"
    reference_audio: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedArtifact:
    """Record of a generated artifact."""
    artifact_id: str
    artifact_type: str  # "image", "video", "audio"
    file_path: str
    spec: dict[str, Any]
    provider: str
    gpu_id: int
    generation_time_seconds: float
    quality_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ═══════════════════════════════════════════════════════════════════════════
# PROVIDER PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════

class ImageProvider(ABC):
    """Protocol for image generation providers."""
    
    @abstractmethod
    def generate(self, spec: ImageSpec) -> GeneratedArtifact:
        """Generate an image from spec."""
        ...
    
    @abstractmethod
    def get_vram_usage(self) -> float:
        """Return VRAM usage in GB."""
        ...
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is ready."""
        ...


class VideoProvider(ABC):
    """Protocol for video generation providers."""
    
    @abstractmethod
    def generate(self, spec: VideoSpec) -> GeneratedArtifact:
        """Generate a video from spec."""
        ...
    
    @abstractmethod
    def image_to_video(self, image_path: str, spec: VideoSpec) -> GeneratedArtifact:
        """Animate a static image into video."""
        ...
    
    @abstractmethod
    def get_vram_usage(self) -> float:
        """Return VRAM usage in GB."""
        ...
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is ready."""
        ...


class VoiceProvider(ABC):
    """Protocol for voice/audio generation providers."""
    
    @abstractmethod
    def generate(self, spec: VoiceSpec) -> GeneratedArtifact:
        """Generate voice audio from spec."""
        ...
    
    @abstractmethod
    def clone_voice(self, reference_audio: str, voice_id: str) -> bool:
        """Clone a voice from reference audio."""
        ...
    
    @abstractmethod
    def get_vram_usage(self) -> float:
        """Return VRAM usage in GB."""
        ...
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is ready."""
        ...


# ═══════════════════════════════════════════════════════════════════════════
# PROVIDER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

class VisualProviderRegistry:
    """Registry for visual providers. Implements Provider Independence."""
    
    _image_providers: dict[str, ImageProvider] = {}
    _video_providers: dict[str, VideoProvider] = {}
    _voice_providers: dict[str, VoiceProvider] = {}
    
    @classmethod
    def register_image(cls, name: str, provider: ImageProvider) -> None:
        cls._image_providers[name] = provider
    
    @classmethod
    def register_video(cls, name: str, provider: VideoProvider) -> None:
        cls._video_providers[name] = provider
    
    @classmethod
    def register_voice(cls, name: str, provider: VoiceProvider) -> None:
        cls._voice_providers[name] = provider
    
    @classmethod
    def get_image(cls, name: Optional[str] = None) -> Optional[ImageProvider]:
        if name:
            return cls._image_providers.get(name)
        # Return first available
        for provider in cls._image_providers.values():
            if provider.is_available():
                return provider
        return None
    
    @classmethod
    def get_video(cls, name: Optional[str] = None) -> Optional[VideoProvider]:
        if name:
            return cls._video_providers.get(name)
        for provider in cls._video_providers.values():
            if provider.is_available():
                return provider
        return None
    
    @classmethod
    def get_voice(cls, name: Optional[str] = None) -> Optional[VoiceProvider]:
        if name:
            return cls._voice_providers.get(name)
        for provider in cls._voice_providers.values():
            if provider.is_available():
                return provider
        return None
    
    @classmethod
    def list_providers(cls) -> dict[str, list[str]]:
        return {
            "image": list(cls._image_providers.keys()),
            "video": list(cls._video_providers.keys()),
            "voice": list(cls._voice_providers.keys()),
        }


# ═══════════════════════════════════════════════════════════════════════════
# OLLAMA IMAGE PROVIDER (Cloud API fallback)
# ═══════════════════════════════════════════════════════════════════════════

class OllamaImageProvider(ImageProvider):
    """Image generation via Ollama-compatible API."""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
    
    def generate(self, spec: ImageSpec) -> GeneratedArtifact:
        raise NotImplementedError("Ollama does not support image generation")
    
    def get_vram_usage(self) -> float:
        return 0.0
    
    def is_available(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# ACE-STEP MUSIC PROVIDER
# ═══════════════════════════════════════════════════════════════════════════

class ACEStepVoiceProvider(VoiceProvider):
    """Music and audio generation via ACE-Step."""
    
    def __init__(self, model_path: str = "/opt/kudbee/models/acestep",
                 venv_path: str = "/opt/kudbee/venv"):
        self.model_path = model_path
        self.venv_path = venv_path
    
    def generate(self, spec: VoiceSpec) -> GeneratedArtifact:
        """Generate music/audio using ACE-Step."""
        start = time.time()
        artifact_id = str(uuid.uuid4())[:12]
        output_path = f"/opt/kudbee/outputs/audio/{artifact_id}.wav"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        cmd = f'''
source {self.venv_path}/bin/activate
cd /opt/kudbee/ACE-Step
python3 -c "
import sys, os
sys.path.insert(0, '/opt/kudbee/ACE-Step')
os.chdir('/opt/kudbee/ACE-Step')
from acestep.pipeline_ace_step import ACEStepPipeline
pipe = ACEStepPipeline(checkpoint_dir='{self.model_path}', dtype='bfloat16')
pipe(
    audio_duration={spec.metadata.get('duration', 30.0)},
    prompt='{spec.text}',
    lyrics='{spec.metadata.get('lyrics', '')}',
    infer_step=20,
    save_path='{output_path}'
)
"
'''
        subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=600)
        
        generation_time = time.time() - start
        
        return GeneratedArtifact(
            artifact_id=artifact_id,
            artifact_type="audio",
            file_path=output_path if os.path.exists(output_path) else "",
            spec=spec.__dict__,
            provider="acestep",
            gpu_id=0,
            generation_time_seconds=generation_time,
        )
    
    def clone_voice(self, reference_audio: str, voice_id: str) -> bool:
        return False  # ACE-Step does not support voice cloning
    
    def get_vram_usage(self) -> float:
        return 8.0
    
    def is_available(self) -> bool:
        return os.path.exists(self.model_path)


# ═══════════════════════════════════════════════════════════════════════════
# QUALITY EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

class QualityEvaluator:
    """Evaluates visual quality of generated artifacts."""
    
    @staticmethod
    def evaluate_image(file_path: str) -> dict[str, Any]:
        """Score an image on technical metrics."""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", file_path
            ], capture_output=True, text=True, timeout=10)
            
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            
            if not streams:
                return {"score": 0, "error": "No streams found"}
            
            stream = streams[0]
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            codec = stream.get("codec_name", "unknown")
            
            file_size = os.path.getsize(file_path)
            
            score = 0.0
            metrics = {}
            
            # Resolution score
            if width >= 1024 and height >= 1024:
                score += 0.4
                metrics["resolution"] = "good"
            elif width >= 512:
                score += 0.2
                metrics["resolution"] = "medium"
            
            # File size score (larger = more detail)
            if file_size > 500000:
                score += 0.3
                metrics["detail"] = "high"
            elif file_size > 100000:
                score += 0.2
                metrics["detail"] = "medium"
            
            # Codec score
            if codec in ("png", "mjpeg"):
                score += 0.3
                metrics["codec"] = "lossless"
            
            return {"score": round(score, 2), "metrics": metrics, "width": width, "height": height}
        except Exception as e:
            return {"score": 0, "error": str(e)}
    
    @staticmethod
    def evaluate_video(file_path: str) -> dict[str, Any]:
        """Score a video on technical metrics."""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ], capture_output=True, text=True, timeout=10)
            
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            
            if not streams:
                return {"score": 0, "error": "No streams found"}
            
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
            
            duration = float(fmt.get("duration", 0))
            width = int(video_stream.get("width", 0)) if video_stream else 0
            height = int(video_stream.get("height", 0)) if video_stream else 0
            fps_parts = video_stream.get("r_frame_rate", "0/1").split("/") if video_stream else ["0", "1"]
            fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 and int(fps_parts[1]) > 0 else 0
            
            score = 0.0
            metrics = {}
            
            # Duration score
            if duration >= 5:
                score += 0.3
                metrics["duration"] = "good"
            elif duration >= 2:
                score += 0.2
                metrics["duration"] = "short"
            
            # Resolution score
            if width >= 1280 and height >= 720:
                score += 0.3
                metrics["resolution"] = "hd"
            elif width >= 640:
                score += 0.2
                metrics["resolution"] = "sd"
            
            # FPS score
            if fps >= 24:
                score += 0.2
                metrics["fps"] = "smooth"
            
            # Audio score
            if audio_stream:
                score += 0.2
                metrics["has_audio"] = True
            
            return {
                "score": round(score, 2),
                "metrics": metrics,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "fps": fps,
                "has_audio": audio_stream is not None
            }
        except Exception as e:
            return {"score": 0, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# ARTIFACT REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════

class ArtifactRegistry:
    """Registers artifacts in Think Box memory."""
    
    def __init__(self, db_path: str = "/opt/kudbee/memory/kudbee.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visual_artifacts (
                artifact_id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                file_path TEXT,
                provider TEXT,
                gpu_id INTEGER,
                generation_time REAL,
                quality_score REAL,
                metadata TEXT,
                created TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    def register(self, artifact: GeneratedArtifact) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO visual_artifacts
            (artifact_id, artifact_type, file_path, provider, gpu_id, generation_time, quality_score, metadata, created)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            artifact.artifact_id, artifact.artifact_type, artifact.file_path,
            artifact.provider, artifact.gpu_id, artifact.generation_time_seconds,
            artifact.quality_score, json.dumps(artifact.metadata), artifact.created_at
        ))
        conn.commit()
        conn.close()


# Register default providers
def register_defaults():
    """Register default visual providers."""
    ace = ACEStepVoiceProvider()
    if ace.is_available():
        VisualProviderRegistry.register_voice("acestep", ace)


register_defaults()
