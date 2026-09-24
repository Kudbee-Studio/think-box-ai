"""Substrate-related env schema (PR #200)."""

from __future__ import annotations

import re

from thinkbox.env_vars.schema import EnvField, EnvValueKind

SUBSTRATE_FIELDS: tuple[EnvField, ...] = (
    EnvField(
        key="UPSTASH_PUBLIC_BOX_URL",
        kind=EnvValueKind.URL,
        required=False,
        sensitive=False,
        description="Upstash Box public URL",
        pattern=re.compile(r"^https://", re.IGNORECASE),
    ),
    EnvField(
        key="UPSTASH_PUBLIC_BOX_TOKEN",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="Box bearer token",
    ),
    EnvField(
        key="THINKBOX_UPCLOUD_API_TOKEN",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="UpCloud control-plane token",
    ),
)
