"""Video generation for AI film production.

Supports multiple backends:
- Wan2.2-TI2V-5B (text/image to video)
- HunyuanVideo (high quality, high VRAM)
- LTX-Video (image to video)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger("thinkbox.video")


@dataclass
class VideoConfig:
    """Configuration for video generation."""

    model: str = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
    height: int = 720
    width: int = 1280
    num_frames: int = 81  # 5s @ 16fps
    fps: int = 16
    guidance_scale: float = 7.5
    num_inference_steps: int = 50
    negative_prompt: str = "blurry, low quality, distorted, static, text, watermark"
    device: str = "cuda"
    dtype: str = "bfloat16"


@dataclass
class GeneratedVideo:
    """Result of video generation."""

    frames: np.ndarray
    fps: int
    width: int
    height: int
    duration: float
    prompt: str
    config: VideoConfig
    metadata: dict[str, Any]


class VideoGenerator:
    """Generate video clips using diffusion models."""

    def __init__(self, config: VideoConfig | None = None):
        self.config = config or VideoConfig()
        self.pipe = None
        self._loaded = False

    def load_model(self) -> None:
        """Load the video generation model into GPU memory."""
        if self._loaded:
            return

        logger.info(f"Loading video model: {self.config.model}")

        try:
            import torch
            from diffusers import DiffusionPipeline

            dtype_map = {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}

            self.pipe = DiffusionPipeline.from_pretrained(
                self.config.model,
                torch_dtype=dtype_map.get(self.config.dtype, torch.bfloat16),
            )
            self.pipe.to(self.config.device)

            self._loaded = True
            logger.info("Video model loaded successfully")

        except ImportError:
            logger.error("diffusers not installed. Run: pip install diffusers transformers accelerate")
            raise
        except Exception as e:
            logger.error(f"Failed to load video model: {e}")
            raise

    def generate_from_text(self, prompt: str) -> GeneratedVideo:
        """Generate video from text prompt."""
        if not self._loaded:
            self.load_model()

        logger.info(f"Generating video: {prompt[:80]}...")

        import torch

        with torch.no_grad():
            result = self.pipe(
                prompt=prompt,
                negative_prompt=self.config.negative_prompt,
                height=self.config.height,
                width=self.config.width,
                num_frames=self.config.num_frames,
                guidance_scale=self.config.guidance_scale,
                num_inference_steps=self.config.num_inference_steps,
            )

        frames = result.frames[0]

        return GeneratedVideo(
            frames=frames,
            fps=self.config.fps,
            width=self.config.width,
            height=self.config.height,
            duration=self.config.num_frames / self.config.fps,
            prompt=prompt,
            config=self.config,
            metadata={"model": self.config.model},
        )

    def generate_from_image(self, prompt: str, image: Any) -> GeneratedVideo:
        """Generate video from text + reference image (image-to-video)."""
        if not self._loaded:
            self.load_model()

        logger.info(f"Generating I2V: {prompt[:80]}...")

        import torch

        with torch.no_grad():
            result = self.pipe(
                prompt=prompt,
                image=image,
                negative_prompt=self.config.negative_prompt,
                height=self.config.height,
                width=self.config.width,
                num_frames=self.config.num_frames,
                guidance_scale=self.config.guidance_scale,
                num_inference_steps=self.config.num_inference_steps,
            )

        frames = result.frames[0]

        return GeneratedVideo(
            frames=frames,
            fps=self.config.fps,
            width=self.config.width,
            height=self.config.height,
            duration=self.config.num_frames / self.config.fps,
            prompt=prompt,
            config=self.config,
            metadata={"model": self.config.model, "mode": "image_to_video"},
        )

    def save_video(self, video: GeneratedVideo, output_path: str) -> str:
        """Save generated video to file."""
        import cv2
        import os

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, video.fps, (video.width, video.height))

        for frame in video.frames:
            frame_uint8 = (frame * 255).astype(np.uint8)
            frame_bgr = cv2.cvtColor(frame_uint8, cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)

        out.release()
        logger.info(f"Video saved: {output_path}")
        return output_path

    def unload(self) -> None:
        """Free GPU memory."""
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            self._loaded = False

            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass


class SceneBatchGenerator:
    """Generate multiple scenes in batch with progress tracking."""

    def __init__(self, generator: VideoGenerator, output_dir: str = "/opt/kudbee/outputs/scenes"):
        self.generator = generator
        self.output_dir = output_dir

    def generate_scenes(self, prompts: list[dict[str, Any]], progress_callback=None) -> list[str]:
        """Generate all scenes from prompts."""
        import os

        os.makedirs(self.output_dir, exist_ok=True)
        output_paths = []

        for i, prompt_data in enumerate(prompts):
            scene_num = prompt_data.get("scene_number", i + 1)
            visual_prompt = prompt_data.get("visual_prompt", "")

            logger.info(f"Generating scene {scene_num}/{len(prompts)}")

            try:
                video = self.generator.generate_from_text(visual_prompt)
                output_path = os.path.join(self.output_dir, f"scene_{scene_num:04d}.mp4")
                self.generator.save_video(video, output_path)
                output_paths.append(output_path)

                if progress_callback:
                    progress_callback(scene_num, len(prompts), output_path)

            except Exception as e:
                logger.error(f"Failed to generate scene {scene_num}: {e}")
                output_paths.append(None)

        return output_paths
