"""Help UX polish — grouped command catalog (PR #180 F15)."""

from __future__ import annotations

from thinkbox.cli_phase3.completion import PHASE3_SUBCOMMANDS


def phase3_help_sections() -> dict[str, tuple[str, ...]]:
    return {
        "introspection": ("status", "profile", "capabilities", "plugins"),
        "output": ("format-demo", "tail"),
        "workflows": ("workflow-run", "cassette-replay", "batch"),
        "jobs": ("job",),
        "shell": ("completion",),
    }


def format_help_catalog() -> str:
    lines = ["KUDBEECLI Phase 3 commands (hermetic):"]
    for section, cmds in phase3_help_sections().items():
        lines.append(f"  [{section}]")
        for c in cmds:
            if c in PHASE3_SUBCOMMANDS:
                lines.append(f"    - {c}")
    return "\n".join(lines)
