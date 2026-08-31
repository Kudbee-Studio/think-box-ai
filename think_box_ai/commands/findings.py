"""Findings commands for Think Box CLI."""

from __future__ import annotations

from pathlib import Path

FINDINGS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "findings"


def list_findings() -> None:
    """List all findings."""
    if not FINDINGS_DIR.exists():
        print("No findings found.")
        return
    for f in sorted(FINDINGS_DIR.glob("*.md")):
        print(f"  {f.name}")


def show_finding(name: str) -> None:
    """Show a finding by name or partial match."""
    matches = list(FINDINGS_DIR.glob(f"*{name}*.md"))
    if not matches:
        print(f"No finding matches: {name}")
        return
    for m in matches:
        print(f"\n{'='*60}")
        print(f"File: {m.name}")
        print(f"{'='*60}")
        print(m.read_text())
