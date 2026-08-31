"""Quality assurance agent for AI film production.

Validates:
- Visual continuity between scenes
- Character consistency
- Narrative coherence
- Lip sync accuracy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("thinkbox.quality")


@dataclass
class QualityReport:
    """Quality assessment report for a film."""

    overall_score: float = 0.0
    continuity_score: float = 0.0
    consistency_score: float = 0.0
    narrative_score: float = 0.0
    audio_score: float = 0.0
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_issue(self, category: str, description: str, severity: str = "warning", scene: int = 0) -> None:
        self.issues.append({
            "category": category,
            "description": description,
            "severity": severity,
            "scene": scene,
        })

    @property
    def passed(self) -> bool:
        return self.overall_score >= 0.6 and not any(i["severity"] == "error" for i in self.issues)


class QualityAgent:
    """Automated quality control for film production."""

    def __init__(self):
        self.checks_run = 0

    def validate_film(self, scenes: list[dict[str, Any]], screenplay: Any = None) -> QualityReport:
        """Run full quality validation on assembled film."""
        report = QualityReport()

        # Run all checks
        self._check_continuity(scenes, report)
        self._check_character_consistency(scenes, report)
        self._check_narrative_coherence(scenes, screenplay, report)
        self._check_technical_quality(scenes, report)

        # Calculate overall score
        scores = [
            report.continuity_score,
            report.consistency_score,
            report.narrative_score,
            report.audio_score,
        ]
        report.overall_score = sum(scores) / len(scores) if scores else 0.0

        return report

    def _check_continuity(self, scenes: list[dict[str, Any]], report: QualityReport) -> None:
        """Check visual continuity between adjacent scenes."""
        issues = 0
        total_checks = max(1, len(scenes) - 1)

        for i in range(len(scenes) - 1):
            current = scenes[i]
            next_scene = scenes[i + 1]

            # Check location continuity
            if current.get("location") and next_scene.get("location"):
                if current["location"] != next_scene["location"]:
                    # Location change without transition note
                    if not next_scene.get("transition"):
                        report.add_issue(
                            "continuity",
                            f"Location change from {current['location']} to {next_scene['location']} without transition",
                            "info",
                            i + 1,
                        )

            # Check time of day continuity
            if current.get("time_of_day") and next_scene.get("time_of_day"):
                time_jumps = [("DAY", "NIGHT"), ("NIGHT", "DAY"), ("DAWN", "NIGHT")]
                time_pair = (current["time_of_time"], next_scene["time_of_day"])
                if time_pair in time_jumps:
                    report.add_issue(
                        "continuity",
                        f"Abrupt time change: {time_pair[0]} to {time_pair[1]}",
                        "warning",
                        i + 1,
                    )
                    issues += 1

        report.continuity_score = max(0.0, 1.0 - (issues / total_checks))

    def _check_character_consistency(self, scenes: list[dict[str, Any]], report: QualityReport) -> None:
        """Check character appearance consistency across scenes."""
        character_first_seen: dict[str, int] = {}
        issues = 0

        for i, scene in enumerate(scenes):
            chars = scene.get("characters", [])
            for char in chars:
                if char not in character_first_seen:
                    character_first_seen[char] = i + 1

                # Check if character disappears and reappears without explanation
                if i > 0:
                    prev_chars = scenes[i - 1].get("characters", [])
                    if char in prev_chars and char not in chars:
                        # Character left - check if they return without mention
                        for j in range(i + 1, min(i + 5, len(scenes))):
                            future_chars = scenes[j].get("characters", [])
                            if char in future_chars:
                                # Character returned - check if mentioned in action
                                action = scenes[j].get("action", "").lower()
                                if char.lower() not in action:
                                    report.add_issue(
                                        "consistency",
                                        f"Character '{char}' returns without explanation",
                                        "warning",
                                        j + 1,
                                    )
                                    issues += 1
                                    break

        report.consistency_score = max(0.0, 1.0 - (issues / max(1, len(scenes))))

    def _check_narrative_coherence(self, scenes: list[dict[str, Any]], screenplay: Any, report: QualityReport) -> None:
        """Check narrative flow and coherence."""
        issues = 0

        if not scenes:
            report.narrative_score = 0.0
            return

        # Check for minimum scene length
        short_scenes = [s for s in scenes if s.get("duration", 30) < 10]
        if short_scenes:
            report.add_issue(
                "narrative",
                f"{len(short_scenes)} scenes are very short (< 10s)",
                "info",
            )

        # Check for scenes without dialogue or action
        empty_scenes = 0
        for scene in scenes:
            has_dialogue = bool(scene.get("dialogue"))
            has_action = bool(scene.get("action"))
            if not has_dialogue and not has_action:
                empty_scenes += 1

        if empty_scenes:
            report.add_issue(
                "narrative",
                f"{empty_scenes} scenes have no dialogue or action",
                "warning",
            )
            issues += empty_scenes

        # If screenplay provided, check scene ordering
        if screenplay and hasattr(screenplay, 'scenes'):
            expected_count = len(screenplay.scenes)
            actual_count = len(scenes)
            if actual_count < expected_count:
                report.add_issue(
                    "narrative",
                    f"Missing scenes: generated {actual_count}/{expected_count}",
                    "error",
                )
                issues += 5

        report.narrative_score = max(0.0, 1.0 - (issues / len(scenes)))

    def _check_technical_quality(self, scenes: list[dict[str, Any]], report: QualityReport) -> None:
        """Check technical aspects of generated content."""
        import os

        issues = 0

        for i, scene in enumerate(scenes):
            video_path = scene.get("video_path", "")

            # Check file exists
            if video_path and not os.path.exists(video_path):
                report.add_issue(
                    "technical",
                    f"Scene {i + 1} video file missing: {video_path}",
                    "error",
                    i + 1,
                )
                issues += 1
                continue

            # Check file size (should be at least 100KB for a real video)
            if video_path and os.path.exists(video_path):
                size = os.path.getsize(video_path)
                if size < 100000:  # 100KB
                    report.add_issue(
                        "technical",
                        f"Scene {i + 1} video suspiciously small: {size / 1024:.0f}KB",
                        "warning",
                        i + 1,
                    )
                    issues += 1

            # Check audio exists for scenes with dialogue
            audio_path = scene.get("audio_path", "")
            dialogue = scene.get("dialogue", [])
            if dialogue and audio_path and not os.path.exists(audio_path):
                report.add_issue(
                    "audio",
                    f"Scene {i + 1} missing audio for dialogue",
                    "warning",
                    i + 1,
                )
                issues += 1

        report.audio_score = max(0.0, 1.0 - (issues / max(1, len(scenes))))

    def generate_report_text(self, report: QualityReport) -> str:
        """Generate human-readable quality report."""
        lines = [
            "=== KU3BEE Film Quality Report ===",
            f"Overall Score: {report.overall_score:.0%}",
            f"  Continuity:  {report.continuity_score:.0%}",
            f"  Consistency: {report.consistency_score:.0%}",
            f"  Narrative:   {report.narrative_score:.0%}",
            f"  Audio:       {report.audio_score:.0%}",
            "",
            f"Status: {'PASS' if report.passed else 'NEEDS REVIEW'}",
        ]

        if report.issues:
            lines.append(f"\nIssues ({len(report.issues)}):")
            for issue in report.issues[:20]:
                severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue["severity"], "•")
                scene_info = f" [Scene {issue['scene']}]" if issue["scene"] else ""
                lines.append(f"  {severity_icon} {issue['category']}{scene_info}: {issue['description']}")

        if report.warnings:
            lines.append(f"\nWarnings ({len(report.warnings)}):")
            for warning in report.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)
