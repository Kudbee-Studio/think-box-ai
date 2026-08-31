"""Voice generation for AI film production.

Supports:
- ElevenLabs (primary, high quality)
- OpenAI TTS (fallback)
- Coqui TTS (self-hosted, free)
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("thinkbox.voice")


@dataclass
class VoiceProfile:
    """Character voice configuration."""

    character_name: str
    voice_id: str = ""
    provider: str = "elevenlabs"
    speed: float = 1.0
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    description: str = ""
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class NarrationSegment:
    """A piece of narration for a scene."""

    scene_number: int
    text: str
    character: str
    emotion: str = "neutral"
    audio_path: str = ""
    duration: float = 0.0


class VoiceGenerator:
    """Generate professional voice narration."""

    EMOTION_MAP = {
        "neutral": {"stability": 0.5, "style": 0.0},
        "happy": {"stability": 0.3, "style": 0.4},
        "sad": {"stability": 0.7, "style": 0.2},
        "angry": {"stability": 0.2, "style": 0.6},
        "fearful": {"stability": 0.3, "style": 0.5},
        "excited": {"stability": 0.2, "style": 0.7},
        "calm": {"stability": 0.8, "style": 0.1},
    }

    def __init__(self, api_key: str = "", provider: str = "elevenlabs"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.provider = provider
        self.voices: dict[str, VoiceProfile] = {}

    def register_voice(self, profile: VoiceProfile) -> None:
        """Register a voice profile for a character."""
        self.voices[profile.character_name] = profile
        logger.info(f"Registered voice for {profile.character_name} (provider={profile.provider})")

    def create_voice_from_description(
        self,
        name: str,
        description: str,
        sample_text: str = "",
    ) -> VoiceProfile:
        """Create a voice profile from character description."""
        if self.provider == "elevenlabs":
            return self._create_elevenlabs_voice(name, description, sample_text)
        else:
            return VoiceProfile(character_name=name, provider=self.provider, description=description)

    def _create_elevenlabs_voice(self, name: str, description: str, sample_text: str) -> VoiceProfile:
        """Create ElevenLabs voice via API."""
        try:
            import requests

            url = "https://api.elevenlabs.io/v1/voices/add"
            headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}

            payload = {
                "name": name,
                "description": description,
                "labels": {"type": "character"},
            }

            # If we have a sample text, use voice design
            if sample_text:
                payload["text"] = sample_text

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                voice_id = data.get("voice_id", "")
                return VoiceProfile(
                    character_name=name,
                    voice_id=voice_id,
                    provider="elevenlabs",
                    description=description,
                )
            else:
                logger.error(f"ElevenLabs voice creation failed: {response.text}")
                return VoiceProfile(character_name=name, provider="elevenlabs", description=description)

        except ImportError:
            logger.error("requests not installed")
            return VoiceProfile(character_name=name, provider="elevenlabs")
        except Exception as e:
            logger.error(f"Voice creation error: {e}")
            return VoiceProfile(character_name=name, provider="elevenlabs")

    def generate_narration(
        self,
        text: str,
        character: str,
        emotion: str = "neutral",
        output_path: str = "",
    ) -> NarrationSegment:
        """Generate narration audio for a character."""
        voice = self.voices.get(character)
        if voice is None:
            voice = VoiceProfile(character_name=character, provider=self.provider)

        if not output_path:
            output_path = tempfile.mktemp(suffix=".mp3", prefix=f"narration_{character}_")

        if voice.provider == "elevenlabs":
            audio_path = self._generate_elevenlabs(text, voice, emotion, output_path)
        elif voice.provider == "openai":
            audio_path = self._generate_openai(text, voice, output_path)
        else:
            audio_path = self._generate_coqui(text, voice, output_path)

        # Estimate duration (rough: ~150 words per minute)
        word_count = len(text.split())
        duration = (word_count / 150) * 60

        return NarrationSegment(
            scene_number=0,
            text=text,
            character=character,
            emotion=emotion,
            audio_path=audio_path,
            duration=duration,
        )

    def _generate_elevenlabs(self, text: str, voice: VoiceProfile, emotion: str, output_path: str) -> str:
        """Generate via ElevenLabs API."""
        try:
            import requests

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice.voice_id}"
            headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}

            emotion_params = self.EMOTION_MAP.get(emotion, self.EMOTION_MAP["neutral"])

            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": emotion_params["stability"],
                    "similarity_boost": voice.similarity_boost,
                    "style": emotion_params["style"],
                    "speed": voice.speed,
                },
            }

            response = requests.post(url, json=payload, headers=headers, timeout=60)

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                logger.error(f"ElevenLabs TTS failed: {response.text}")
                return ""

        except ImportError:
            logger.error("requests not installed")
            return ""
        except Exception as e:
            logger.error(f"ElevenLabs error: {e}")
            return ""

    def _generate_openai(self, text: str, voice: VoiceProfile, output_path: str) -> str:
        """Generate via OpenAI TTS API."""
        try:
            import openai

            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            response = client.audio.speech.create(model="tts-1-hd", voice="nova", input=text)

            response.stream_to_file(output_path)
            return output_path

        except ImportError:
            logger.error("openai not installed")
            return ""
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return ""

    def _generate_coqui(self, text: str, voice: VoiceProfile, output_path: str) -> str:
        """Generate via Coqui TTS (self-hosted)."""
        try:
            from TTS.api import TTS

            tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
            tts.tts_to_file(text=text, file_path=output_path)
            return output_path

        except ImportError:
            logger.error("TTS (coqui) not installed")
            return ""
        except Exception as e:
            logger.error(f"Coqui TTS error: {e}")
            return ""


class FilmVoiceDirector:
    """Manage all voice production for a film."""

    def __init__(self, generator: VoiceGenerator, output_dir: str = "/opt/kudbee/outputs/audio"):
        self.generator = generator
        self.output_dir = output_dir

    def produce_scene_narration(self, scene_data: dict[str, Any]) -> list[NarrationSegment]:
        """Generate all narration for a scene."""
        import os

        os.makedirs(self.output_dir, exist_ok=True)

        segments = []
        dialogue = scene_data.get("dialogue", [])
        scene_num = scene_data.get("scene_number", 0)

        for line in dialogue:
            speaker = line.get("speaker", "NARRATOR")
            text = line.get("text", "")

            if not text:
                continue

            emotion = self._detect_emotion(text)
            output_path = os.path.join(self.output_dir, f"scene_{scene_num:04d}_{speaker}.mp3")

            segment = self.generator.generate_narration(text, speaker, emotion, output_path)
            segment.scene_number = scene_num
            segments.append(segment)

        return segments

    def _detect_emotion(self, text: str) -> str:
        """Simple emotion detection from text."""
        text_lower = text.lower()

        if any(w in text_lower for w in ["!", "wow", "amazing", "incredible"]):
            return "excited"
        if any(w in text_lower for w in ["?", "what", "how", "why", "confused"]):
            return "fearful"
        if any(w in text_lower for w in ["hate", "angry", "furious", "never"]):
            return "angry"
        if any(w in text_lower for w in ["sad", "sorry", "miss", "lost"]):
            return "sad"
        if any(w in text_lower for w in ["happy", "great", "love", "wonderful"]):
            return "happy"

        return "neutral"
