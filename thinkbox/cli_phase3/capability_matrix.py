"""Capability matrix and feature flags for CLI (PR #180 F17)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityRow:
    capability: str
    phase2: bool
    phase3: bool
    live_required: bool


def build_capability_matrix() -> tuple[CapabilityRow, ...]:
    return (
        CapabilityRow("inspect", True, True, False),
        CapabilityRow("dry_run", True, True, False),
        CapabilityRow("receipt_bind", True, True, False),
        CapabilityRow("job_mirror", False, True, False),
        CapabilityRow("cassette_replay", False, True, False),
        CapabilityRow("swarm_live", True, True, True),
    )


def feature_flags() -> dict[str, bool]:
    return {
        "cli_phase3_enabled": True,
        "cli_phase3_batch": True,
        "cli_phase3_sdk_bridge": True,
        "cli_live_swarm": False,
    }
