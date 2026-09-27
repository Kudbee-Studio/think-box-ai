"""Dry-run receipt deepen (PR #186 F17)."""
from __future__ import annotations

def dry_run_skips_persist(dry_run: bool) -> bool:
    return dry_run
