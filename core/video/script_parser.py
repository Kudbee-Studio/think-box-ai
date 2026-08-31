"""Script parser for AI film production.

Parses structured screenplays into generation-ready scene prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Character:
    name: str
    description: str = ""
    voice_profile: str = ""
    aliases: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        """Check if this character appears in text."""
        text_upper = text.upper()
        if self.name.upper() in text_upper:
            return True
        return any(alias.upper() in text_upper for alias in self.aliases)


@dataclass
class Scene:
    number: int
    heading: str
    location: str
    time_of_day: str
    action: str
    dialogue: list[dict[str, str]]
    characters_present: list[str]
    duration_estimate: float = 30.0  # seconds
    prompt: dict[str, Any] = field(default_factory=dict)


@dataclass
class Screenplay:
    title: str
    logline: str
    characters: list[Character]
    scenes: list[Scene]
    total_duration: float = 0.0


class ScriptParser:
    """Parse screenplay text into structured screenplay object."""

    SCENE_HEADING_PATTERN = re.compile(
        r"^(INT\.|EXT\.|INT\./EXT\.|EXT\./INT\.)\s+(.+?)\s*-\s*(DAY|NIGHT|DUSK|DAWN|CONTINUOUS|MORNING|EVENING|LATER|SAME TIME)",
        re.MULTILINE | re.IGNORECASE,
    )

    CHARACTER_CUE_PATTERN = re.compile(r"^\s*([A-Z][A-Z\s]+)(?:\s*\(.+?\))?\s*$", re.MULTILINE)

    DIALOGUE_PATTERN = re.compile(
        r"^\s*([A-Z][A-Z\s]+)(?:\s*\(.+?\))?\s*\n\s*(.+?)(?=\n\s*\n|\n\s*[A-Z][A-Z]+\s*$)",
        re.MULTILINE | re.DOTALL,
    )

    PARENTHETICAL_PATTERN = re.compile(r"\((.+?)\)")

    TRANSITION_PATTERN = re.compile(r"^(CUT TO:|FADE TO:|DISSOLVE TO:|FADE OUT\.|SMASH CUT TO:|MATCH CUT TO:)", re.MULTILINE)

    def parse(self, script_text: str, title: str = "Untitled", logline: str = "") -> Screenplay:
        """Parse raw screenplay text into structured screenplay."""
        lines = script_text.strip().split("\n")

        characters = self._extract_characters(script_text)
        scenes = self._extract_scenes(script_text, characters)

        total_duration = sum(s.duration_estimate for s in scenes)

        return Screenplay(
            title=title,
            logline=logline,
            characters=characters,
            scenes=scenes,
            total_duration=total_duration,
        )

    def _extract_characters(self, script: str) -> list[Character]:
        """Extract character names from script cues."""
        characters = []
        seen = set()

        for match in self.CHARACTER_CUE_PATTERN.finditer(script):
            name = match.group(1).strip()
            if name in seen or len(name) < 2:
                continue
            if name.startswith(("INT", "EXT", "FADE", "CUT", "DISSOLVE", "ANGLE")):
                continue
            seen.add(name)
            characters.append(Character(name=name, aliases=[name.split()[0]]))

        return characters

    def _extract_scenes(self, script: str, characters: list[Character]) -> list[Scene]:
        """Extract individual scenes from script."""
        scenes = []
        scene_matches = list(self.SCENE_HEADING_PATTERN.finditer(script))

        for i, match in enumerate(scene_matches):
            location = match.group(2).strip()
            time_of_day = match.group(3).strip()

            # Scene content is from this heading to the next
            start = match.end()
            end = scene_matches[i + 1].start() if i + 1 < len(scene_matches) else len(script)
            content = script[start:end].strip()

            # Extract dialogue
            dialogue = self._extract_dialogue(content)

            # Find characters present
            chars_present = []
            for char in characters:
                if char.matches(content):
                    chars_present.append(char.name)

            # Estimate duration: ~150 words per minute of screen time
            word_count = len(content.split())
            duration = max(10.0, min(60.0, word_count / 2.5))

            scenes.append(
                Scene(
                    number=i + 1,
                    heading=match.group(0).strip(),
                    location=location,
                    time_of_day=time_of_day,
                    action=self._extract_action(content),
                    dialogue=dialogue,
                    characters_present=chars_present,
                    duration_estimate=duration,
                )
            )

        return scenes

    def _extract_dialogue(self, scene_content: str) -> list[dict[str, str]]:
        """Extract dialogue blocks from scene content."""
        dialogue = []

        for match in self.DIALOGUE_PATTERN.finditer(scene_content):
            speaker = match.group(1).strip()
            text = match.group(2).strip()

            # Skip scene headings and transitions
            if speaker.startswith(("INT", "EXT", "FADE", "CUT")):
                continue

            # Clean parentheticals from dialogue
            clean_text = self.PARENTHETICAL_PATTERN.sub("", text).strip()

            if clean_text:
                dialogue.append({"speaker": speaker, "text": clean_text})

        return dialogue

    def _extract_action(self, scene_content: str) -> str:
        """Extract action/description lines (non-dialogue)."""
        lines = []
        for line in scene_content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip character cues and dialogue
            if self.CHARACTER_CUE_PATTERN.match(stripped):
                continue
            if stripped.startswith(("INT.", "EXT.", "FADE")):
                continue
            lines.append(stripped)

        return "\n".join(lines[:5])  # First 5 action lines as summary


class PromptGenerator:
    """Generate video generation prompts from parsed scenes."""

    CINEMATIC_STYLES = {
        "drama": "cinematic drama, natural lighting, shallow depth of field, film grain",
        "action": "dynamic action, fast cuts, dramatic lighting, high contrast",
        "scifi": "science fiction, neon lighting, futuristic, volumetric fog",
        "horror": "horror atmosphere, dark shadows, cold color palette, tension",
        "comedy": "bright lighting, warm tones, comedic timing, clean composition",
        "romance": "soft focus, warm golden hour, intimate framing, gentle lighting",
    }

    CAMERA_MOVEMENTS = [
        "static wide shot",
        "slow push in",
        "pan left to right",
        "tracking shot following subject",
        "overhead bird's eye",
        "low angle looking up",
        "dolly zoom",
        "crane shot descending",
    ]

    def generate_prompts(self, screenplay: Screenplay) -> list[dict[str, Any]]:
        """Generate video prompts for all scenes."""
        prompts = []

        for scene in screenplay.scenes:
            prompt = self._scene_to_prompt(scene, screenplay)
            prompts.append(prompt)

        return prompts

    def _scene_to_prompt(self, scene: Scene, screenplay: Screenplay) -> dict[str, Any]:
        """Convert a single scene to a video generation prompt."""
        # Determine genre/style
        genre = self._detect_genre(scene.action)
        style = self.CINEMATIC_STYLES.get(genre, self.CINEMATIC_STYLES["drama"])

        # Build character descriptions
        char_descs = []
        for char_name in scene.characters_present:
            char = next((c for c in screenplay.characters if c.name == char_name), None)
            if char and char.description:
                char_descs.append(f"{char_name}: {char.description}")

        # Build visual prompt
        visual_parts = [
            style,
            f"{scene.location}, {scene.time_of_day}",
            scene.action[:200],  # Truncate for prompt length
        ]

        if char_descs:
            visual_parts.append("Characters: " + "; ".join(char_descs))

        camera = self.CAMERA_MOVEMENTS[scene.number % len(self.CAMERA_MOVEMENTS)]

        return {
            "scene_number": scene.number,
            "heading": scene.heading,
            "visual_prompt": ", ".join(visual_parts),
            "camera": camera,
            "duration": scene.duration_estimate,
            "characters": scene.characters_present,
            "dialogue": scene.dialogue,
            "narration": self._generate_narration(scene),
        }

    def _detect_genue(self, text: str) -> str:
        """Detect genre from scene text."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["explosion", "chase", "fight", "gun", "running"]):
            return "action"
        if any(w in text_lower for w in ["spaceship", "robot", "alien", "future", "tech"]):
            return "scifi"
        if any(w in text_lower for w in ["scream", "blood", "dark", "shadow", "fear"]):
            return "horror"
        if any(w in text_lower for w in ["laugh", "smile", "funny", "comedy"]):
            return "comedy"
        if any(w in text_lower for w in ["love", "kiss", "embrace", "heart"]):
            return "romance"
        return "drama"

    def _generate_narration(self, scene: Scene) -> str:
        """Generate narration text for a scene."""
        parts = []
        if scene.action:
            parts.append(scene.action[:300])
        for d in scene.dialogue:
            parts.append(f"{d['speaker']}: {d['text']}")
        return " ".join(parts)


def parse_screenplay(script_text: str, title: str = "Untitled", logline: str = "") -> Screenplay:
    """Convenience function to parse a screenplay."""
    return ScriptParser().parse(script_text, title, logline)


def generate_prompts(screenplay: Screenplay) -> list[dict[str, Any]]:
    """Convenience function to generate prompts from a screenplay."""
    return PromptGenerator().generate_prompts(screenplay)


if __name__ == "__main__":
    # Example usage
    sample_script = """
FADE IN:

INT. COFFEE SHOP - MORNING

Sunlight streams through large windows. SARAH (30s, professional) sits alone at a corner table, staring at her laptop.

SARAH
(muttering to herself)
This can't be right. The numbers don't add up.

The door opens. MARCUS (40s, confident) enters, scanning the room. He spots Sarah and walks over.

MARCUS
Sarah? I got your message. What's so urgent?

SARAH
Look at this. Someone's been siphoning funds for months.

Marcus sits down, his expression darkening as he reviews the screen.

MARCUS
We need to move fast. Before they know we're onto them.

FADE OUT.
"""

    parser = ScriptParser()
    screenplay = parser.parse(sample_script, title="The Embezzlement", logline="A financial analyst uncovers corporate fraud")

    print(f"Title: {screenplay.title}")
    print(f"Characters: {[c.name for c in screenplay.characters]}")
    print(f"Scenes: {len(screenplay.scenes)}")
    print(f"Estimated duration: {screenplay.total_duration:.0f}s")

    for scene in screenplay.scenes:
        print(f"\n--- Scene {scene.number} ---")
        print(f"Location: {scene.location}")
        print(f"Time: {scene.time_of_day}")
        print(f"Characters: {scene.characters_present}")
        print(f"Duration: {scene.duration_estimate:.0f}s")
        if scene.dialogue:
            for d in scene.dialogue:
                print(f"  {d['speaker']}: {d['text'][:50]}...")

    print("\n--- Generated Prompts ---")
    prompts = generate_prompts(screenplay)
    for p in prompts:
        print(f"\nScene {p['scene_number']}:")
        print(f"  Visual: {p['visual_prompt'][:100]}...")
        print(f"  Camera: {p['camera']}")
        print(f"  Duration: {p['duration']:.0f}s")
