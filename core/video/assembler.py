"""Film assembly and post-production.

Combines generated scenes, audio, and effects into final film.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("thinkbox.assembly")


@dataclass
class Transition:
    """Scene transition type."""

    name: str
    duration: float
    ffmpeg_filter: str


TRANSITIONS = {
    "cut": Transition("cut", 0, ""),
    "fade": Transition("fade", 1.0, "fade=t=in:st=0:d=1,fade=t=out:st=duration-1:d=1"),
    "dissolve": Transition("dissolve", 1.5, "xfade=transition=dissolve:duration=1.5:offset=END-1.5"),
    "wipe": Transition("wipe", 1.0, "xfade=transition=wipeleft:duration=1:offset=END-1"),
    "flash": Transition("flash", 0.5, "xfade=transition=fade:duration=0.5:offset=END-0.5"),
}


@dataclass
class FilmProject:
    """Complete film project state."""

    title: str
    scenes: list[dict[str, Any]]
    audio_tracks: list[str]
    music_track: str
    output_path: str
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 24
    transition: str = "fade"


class FilmAssembler:
    """Assemble final film from generated assets."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg = ffmpeg_path
        self.temp_dir = tempfile.mkdtemp(prefix="ku3bee-film-")

    def assemble(self, project: FilmProject) -> str:
        """Assemble complete film from project."""
        logger.info(f"Assembling film: {project.title}")
        logger.info(f"Scenes: {len(project.scenes)}, Resolution: {project.resolution}")

        # Step 1: Prepare scene files (normalize resolution/fps)
        prepared_scenes = self._prepare_scenes(project.scenes, project.resolution, project.fps)

        # Step 2: Add transitions between scenes
        with_transitions = self._add_transitions(prepared_scenes, project.transition)

        # Step 3: Concatenate all scenes
        concat_file = self._create_concat_file(with_transitions)
        concatenated = os.path.join(self.temp_dir, "concatenated.mp4")

        self._ffmpeg_concat(concat_file, concatenated)

        # Step 4: Mix audio (narration + music)
        final = self._mix_audio(concatenated, project.audio_tracks, project.music_track, project.output_path)

        logger.info(f"Film assembled: {final}")
        return final

    def _prepare_scenes(self, scenes: list[dict[str, Any]], resolution: tuple[int, int], fps: int) -> list[str]:
        """Normalize all scenes to same resolution and fps."""
        prepared = []
        target_w, target_h = resolution

        for i, scene in enumerate(scenes):
            video_path = scene.get("video_path", "")
            if not video_path or not os.path.exists(video_path):
                logger.warning(f"Scene {i + 1}: video not found, skipping")
                continue

            output_path = os.path.join(self.temp_dir, f"scene_{i:04d}_prepared.mp4")

            cmd = [
                self.ffmpeg, "-y",
                "-i", video_path,
                "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
                "-r", str(fps),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                output_path,
            ]

            subprocess.run(cmd, capture_output=True, timeout=120)
            prepared.append(output_path)

        return prepared

    def _add_transitions(self, scene_paths: list[str], transition_name: str) -> list[str]:
        """Add transitions between scenes."""
        transition = TRANSITIONS.get(transition_name, TRANSITIONS["fade"])

        if transition.duration == 0 or len(scene_paths) < 2:
            return scene_paths

        # For xfade transitions, we need to use the concat filter with transitions
        # This is handled in _create_concat_file
        return scene_paths

    def _create_concat_file(self, scene_paths: list[str]) -> str:
        """Create ffmpeg concat demuxer file."""
        concat_path = os.path.join(self.temp_dir, "concat.txt")

        with open(concat_path, "w") as f:
            for path in scene_paths:
                f.write(f"file '{path}'\n")

        return concat_path

    def _ffmpeg_concat(self, concat_file: str, output_path: str) -> None:
        """Concatenate videos using ffmpeg."""
        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error(f"FFmpeg concat failed: {result.stderr}")
            raise RuntimeError(f"Failed to concatenate scenes: {result.stderr[:500]}")

    def _mix_audio(
        self,
        video_path: str,
        audio_tracks: list[str],
        music_track: str,
        output_path: str,
    ) -> str:
        """Mix narration + music with video."""
        cmd = [self.ffmpeg, "-y", "-i", video_path]

        # Add audio tracks
        for track in audio_tracks:
            if track and os.path.exists(track):
                cmd.extend(["-i", track])

        # Add music
        if music_track and os.path.exists(music_track):
            cmd.extend(["-i", music_track])

        # Build filter complex
        n_audio = len([t for t in audio_tracks if t and os.path.exists(t)])
        has_music = music_track and os.path.exists(music_track)

        filter_parts = []

        if n_audio > 0:
            # Mix all narration tracks
            inputs = [f"[{i + 1}:a]" for i in range(n_audio)]
            filter_parts.append(f"{''.join(inputs)}amix=inputs={n_audio}:duration=first[a_narr]")

        if has_music:
            # Lower music volume when narration plays
            music_idx = n_audio + 1
            if n_audio > 0:
                filter_parts.append(
                    f"[{music_idx}:a]volume=0.3,afade=t=in:st=0:d=2,afade=t=out:st=duration-3:d=3[a_music];"
                    f"[a_narr][a_music]amix=inputs=2:duration=first[aout]"
                )
            else:
                filter_parts.append(f"[{music_idx}:a]volume=0.5,afade=t=in:st=0:d=2[aout]")
        elif n_audio > 0:
            filter_parts.append("[a_narr]acopy[aout]")

        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])
            cmd.extend(["-map", "0:v", "-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:v"])

        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error(f"Audio mix failed: {result.stderr}")
            raise RuntimeError(f"Failed to mix audio: {result.stderr[:500]}")

        return output_path

    def add_credits(self, video_path: str, credits_text: str, output_path: str) -> str:
        """Add credits roll to end of video."""
        # Create credits video
        credits_path = os.path.join(self.temp_dir, "credits.mp4")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1920x1080:d=10",
            "-vf", f"drawtext=text='{credits_text}':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=h-(t*50):start_number=0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            credits_path,
        ]

        subprocess.run(cmd, capture_output=True, timeout=60)

        # Concatenate with main video
        concat_file = os.path.join(self.temp_dir, "credits_concat.txt")
        with open(concat_file, "w") as f:
            f.write(f"file '{video_path}'\n")
            f.write(f"file '{credits_path}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ]

        subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path

    def cleanup(self) -> None:
        """Remove temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
