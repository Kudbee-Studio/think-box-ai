"""Governance env schema (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.schema import EnvField, EnvValueKind

GOVERNANCE_FIELDS: tuple[EnvField, ...] = (
    EnvField(
        key="THINKBOX_SWARM_LIVE_ACK",
        kind=EnvValueKind.BOOL,
        required=False,
        sensitive=True,
        description="Founder live-swarm acknowledgment",
    ),
    EnvField(
        key="THINKBOX_GOVERNANCE_TOKEN",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="Governance admission token",
    ),
    EnvField(
        key="THINKBOX_KILO_CLAIM_LIVE",
        kind=EnvValueKind.BOOL,
        required=False,
        sensitive=False,
        description="Must not affirm LIVE VERIFIED via env",
        default="false",
    ),
)
